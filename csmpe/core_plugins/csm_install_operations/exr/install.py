# coding=utf-8
# =============================================================================
#
# Copyright (c) 2016, Cisco Systems
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.
# =============================================================================
import re
import time
import os
import json
from condoor import ConnectionError
from csmpe.core_plugins.csm_node_status_check.exr.plugin_lib import parse_show_platform

install_error_pattern = re.compile("Error:    (.*)$", re.MULTILINE)

plugin_ctx = None
last_opid = 0

def log_install_errors(ctx, output):
        errors = re.findall(install_error_pattern, output)
        for line in errors:
            ctx.warning(line)


def check_ncs6k_release(ctx):
    """
    Only release 5.2.5 and above are supported by the plugin.
    """
    if ctx.family == 'NCS6K':
        packages = ctx.software_packages
        if packages is not None:
            for package_name in packages:
                matches = re.findall("\d+\.\d+\.\d+", package_name)
                if matches:
                    if matches[0] < '5.2.5':
                        ctx.error('Abort: Software package earlier than release 5.2.5 for NCS6K is not supported.')


def watch_operation(ctx, op_id=0):
    """
    Watch for the non-reload situation.  Upon issuing add/activate/commit/remove/deactivate, the install operation
    will be executed in the background.  The following message

    Install operation will continue in the background

    will be displayed.  After some time elapses, a successful or abort message will be displayed.

    The CLI command, 'show install request' is used in the loop to report the progress percentages.  Upon
    completion, 'show install request' returns 'No install operation in progress'.  The watch_operation will be
    done at that point.

    As an example,

    RP/0/RP0/CPU0:Deploy#install deactivate ncs6k-5.2.5.CSCuz65240-1.0.0
    May 31 20:14:14 Install operation 3 started by root:
      install deactivate pkg ncs6k-5.2.5.CSCuz65240-1.0.0
    May 31 20:14:14 Package list:
    May 31 20:14:14     ncs6k-5.2.5.CSCuz65240-1.0.0
    May 31 20:14:20 Install operation will continue in the background

    <--- Time Lapse --->

    RP/0/RP0/CPU0:Deploy#May 31 20:15:10 Install operation 3 finished successfully

    ------------------------------------------------------------------------------------------------------------
    RP/0/RP0/CPU0:Deploy#show install request
    The install operation 17 is 30% complete

    or

    RP/0/RP0/CPU0:Deploy#show install request
    No install operation in progress

    When install is completed, the following message will be displayed

    ------------------------------------------------------------------------------------------------------------
    If the install operation is successful, the following message will be displayed.

    RP/0/RP0/CPU0:Deploy#May 24 22:25:43 Install operation 17 finished successfully
    """
    no_install = r"No install operation in progress"
    # In ASR9K eXR, the output to show install request may be "The install prepare operation 9 is 40% complete"
    # or "The install service operation 9 is 40% complete" or "The install add operation 9 is 40% complete" and etc.
    op_progress = r"The install \w*?\s?operation {} is (\d+)% complete".format(op_id)
    success = "Install operation {} finished successfully".format(op_id)
    admin_success = "Install operation {} completed successfully".format(op_id)
    cmd_show_install_request = "show install request"
    ctx.info("Watching the operation {} to complete".format(op_id))
    ctx.op_id = op_id
    last_status = None
    finish = False
    time_tried = 0
    while not finish:
        try:
            try:
                # this is to catch the successful operation as soon as possible
#                ctx.send("", wait_for_string=success, timeout=20)
                ctx.send("", wait_for_string=admin_success, timeout=20)
                finish = True
            except ctx.CommandTimeoutError:
                pass

            message = ""
            output = ctx.send(cmd_show_install_request, timeout=300)
            if op_id in output:
                result = re.search(op_progress, output)
                if result:
                    status = result.group(0)
                    message = "{}".format(status)

                if message != last_status:
                    ctx.post_status(message)
                    last_status = message
        except (ConnectionError, ctx.CommandTimeoutError) as e:
            if time_tried > 2:
                raise e

            time_tried += 1
            ctx.disconnect()
            time.sleep(60)
            ctx.reconnect()

        if no_install in output:
            break

    report_install_status(ctx, op_id)


def validate_node_state(inventory):
    valid_state = [
        'IOS XR RUN',
        'PRESENT',
        'READY',
        'FAILED',
        'OK',
        'DISABLED',
        'UNPOWERED',
        'ADMIN DOWN',
        'OPERATIONAL',
        'NOT ALLOW ONLIN',  # This is not spelling error
    ]

    for key, value in inventory.items():
        if 'CPU' in key:
            if value['state'] not in valid_state:
                break
    else:
        return True

    return False


def wait_for_reload(ctx):
    """
     Wait for system to come up with max timeout as 25 Minutes

    """
    ctx.info("Device or sdr is reloading.")
    ctx.post_status("Device or sdr is reloading...")
    ctx.disconnect()
    time.sleep(60)
    ctx.reconnect(max_timeout=1500)  # 25 * 60 = 1500

    timeout = 3600
    poll_time = 30
    time_waited = 0
    xr_run = "IOS XR RUN"

    cmd = "show platform"
    ctx.info("Waiting for all nodes to come up")
    ctx.post_status("Waiting for all nodes to come up")

    time.sleep(100)

    while 1:
        # Wait till all nodes are in XR run state
        time_waited += poll_time
        if time_waited >= timeout:
            break

        time.sleep(poll_time)
        output = ctx.send(cmd)
        if xr_run in output:
            inventory = parse_show_platform(output)
            if validate_node_state(inventory):
                ctx.info("All nodes in desired state")
                return True

    # Some nodes did not come to run state

    report_log(ctx, False, "Not all nodes have come up: {}".format(output)) 
    ctx.error("Not all nodes have come up: {}".format(output))
    # this will never be executed
    return False


def observe_install_add_remove(ctx, output, has_tar=False):
    """
    Success Condition:
    ADD:
    install add source tftp://223.255.254.254/auto/tftpboot-users/alextang/ ncs6k-mpls.pkg-6.1.0.07I.DT_IMAGE
    May 24 18:54:12 Install operation will continue in the background
    RP/0/RP0/CPU0:Deploy#May 24 18:54:30 Install operation 12 finished successfully

    REMOVE:
    RP/0/RP0/CPU0:Deploy#install remove ncs6k-5.2.5.47I.CSCux97367-0.0.15.i
    May 23 21:20:28 Install operation 2 started by root:
      install remove ncs6k-5.2.5.47I.CSCux97367-0.0.15.i
    May 23 21:20:28 Package list:
    May 23 21:20:28     ncs6k-5.2.5.47I.CSCux97367-0.0.15.i
    May 23 21:20:29 Install operation will continue in the background

    RP/0/RP0/CPU0:Deploy#May 23 21:20:29 Install operation 2 finished successfully

    Failed Condition:
    RP/0/RSP0/CPU0:CORFU#install remove ncs6k-5.2.5.47I.CSCux97367-0.0.15.i
    Mon May 23 22:57:45.078 UTC
    May 23 22:57:46 Install operation 28 started by iox:
      install remove ncs6k-5.2.5.47I.CSCux97367-0.0.15.i
    May 23 22:57:46 Package list:
    May 23 22:57:46     ncs6k-5.2.5.47I.CSCux97367-0.0.15.i
    May 23 22:57:47 Install operation will continue in the background

    RP/0/RSP0/CPU0:CORFU#May 23 22:57:48 Install operation 28 aborted
    """
    result = re.search('Install operation (\d+)', output)
    if result:
        op_id = result.group(1)
        if has_tar is True:
            ctx.operation_id = op_id
            ctx.info("The operation {} stored".format(op_id))
    else:
        log_install_errors(ctx, output)
        status, message = match_pattern(ctx.pattern, output)
        report_log(ctx, status, message) 
        ctx.info("Operation failed")
        return  # for sake of clarity

    op_success = "Install operation will continue in the background"

    if op_success in output:
        watch_operation(ctx, op_id)
    else:
        status, message = match_pattern(ctx.pattern, output)
        report_log(ctx, status, message) 
        log_install_errors(ctx, output)
        ctx.error("Operation {} failed".format(op_id))


def get_op_id(output):
    """
    :param output: Output from the install command
    :return: the operational ID
    """
    global plugin_ctx
    result = re.search('nstall operation (\d+)', output)
    if result:
        return result.group(1)
    else:
        op_progress = r"User admin, Op Id (\d+)"
        cmd_show_install_request = "show install request"
        output = plugin_ctx.send(cmd_show_install_request, timeout=300)
        result = re.search(op_progress, output)
        if result:
            plugin_ctx.op_id = result.group(1)
            return plugin_ctx.op_id
    return -1

def report_log(ctx, status, message):
    data = {}
    data['TC'] = ctx.tc_name
    data['tc_id'] = ctx.tc_id
    data['status'] = 'Pass' if status else 'Fail'
    data['message'] = message
    result_file = os.path.join(ctx.log_directory, 'result.log')
    is_append = os.path.isfile(result_file)
    with open(result_file, 'a') as fd_log:
        if is_append:
            fd_log.write(",\n")
        fd_log.write(json.dumps(data, indent=4))
    ctx.post_status("tc_id: {}, TC: {} :: {}".format(ctx.tc_id, ctx.tc_name, message))

def report_install_status(ctx, op_id):
    """
    :param ctx: CSM Context object
    :param op_id: operational ID
    Peeks into the install log to see if the install operation is successful or not
    """
    failed_oper = r'Install operation {} aborted'.format(op_id)
    output = ctx.send("show install log {} detail".format(op_id))
    status, message = match_pattern(ctx.pattern, output)
    report_log(ctx, status, message) 
    if re.search(failed_oper, output):
        log_install_errors(ctx, output)
        ctx.error("Operation {} failed".format(op_id))
        return False
    ctx.info("Operation {} finished successfully".format(op_id))
    return True

def handle_aborted(fsm_ctx):
    """
    :param ctx: FSM Context
    :return: True if successful other False
    """
    global plugin_ctx

    report_install_status(ctx=plugin_ctx, op_id=get_op_id(fsm_ctx.ctrl.before))

    # Indicates the failure
    return False


def handle_non_reload_activate_deactivate(fsm_ctx):
    """
    :param ctx: FSM Context
    :return: True if successful other False
    """
    global plugin_ctx
    global last_opid
    op_id = get_op_id(fsm_ctx.ctrl.before)
    last_opid = op_id 
    if op_id == -1:
        #TODO Scenario : install prepare issu with host and sysadmin no op id is 
        #generated and it fails. Need a way to get the error message and display
        plugin_ctx.error("got -1 as op_id")
        status, message = match_pattern(plugin_ctx.pattern, fsm_ctx.ctrl.before)
        report_log(plugin_ctx, status, message) 
        return False
    nextlevel = plugin_ctx.nextlevel
    if nextlevel:
        next_level_processing(plugin_ctx)
    watch_operation(plugin_ctx, op_id)
    status = report_install_status(plugin_ctx, op_id)
    if status:
        plugin_ctx.info("Operation {} finished successfully".format(op_id))
    return status


def handle_reload_activate_deactivate(fsm_ctx):
    """
    :param ctx: FSM Context
    :return: True if successful other False
    """
    global plugin_ctx
    op_id = get_op_id(fsm_ctx.ctrl.before)
    if op_id == -1:
        status, message = match_pattern(plugin_ctx.pattern, fsm_ctx.ctrl.before)
        report_log(plugin_ctx, status, message) 
        return False
    else:
        plugin_ctx.info("Operation id is {}".format(op_id))
        nextlevel = plugin_ctx.nextlevel
    if nextlevel:
        next_level_processing(plugin_ctx)
    try:
        watch_operation(plugin_ctx, op_id)
    except plugin_ctx.CommandTimeoutError:
        plugin_ctx.info("The device already started the reload")
        pass

    success = wait_for_reload(plugin_ctx)
    if not success:
        report_log(ctx, False, "Reload or boot failure") 
        plugin_ctx.error("Reload or boot failure")
        return False

    #Validate if the operation was really successful
    if plugin_ctx.shell == "Admin" and plugin_ctx.issu_mode:
        output = plugin_ctx.send("admin", timeout=30)
    status = report_install_status(plugin_ctx, op_id)
    if plugin_ctx.shell == "Admin" and plugin_ctx.issu_mode:
        output = plugin_ctx.send("exit", timeout=30)    
    if status:
        plugin_ctx.info("Operation {} finished successfully".format(op_id))
    return status

def no_impact_warning(fsm_ctx):
    plugin_ctx.warning("This was a NO IMPACT OPERATION. Packages are already active on device.")
    nextlevel = plugin_ctx.nextlevel
    if nextlevel:
        next_level_processing(plugin_ctx)
    return True

def handle_done(self, fsm_ctx):
    return True

def handle_hw_modify_cmd(fsm_ctx):
    global plugin_ctx
    op_id = get_op_id(fsm_ctx.ctrl.before)
    if op_id == -1:
        return False
    plugin_ctx.send("yes\r\n", timeout=30)
    # give hw 5 mins to stabilize

    time.sleep(300)

    plugin_ctx.info("Operation {} finished successfully".format(self.op_id))
    return True

def handle_confirm(fsm_ctx):
    global plugin_ctx
    plugin_ctx.send("yes\r\n", timeout=30)
    return True

def get_pkgs(ctx, id):
    cmd = "show install log " + str(id)
    paragraph = ctx.send(cmd, timeout=30)
    ctx.info(paragraph)
    lines = []
    for line in paragraph.split("\n"):
        lines.append(line[16:])
        st = 0
        end = 0

    for idx, line in enumerate(lines):
        if "Packages skipped" in line:
            st = idx
        if "Packages added:" in line:
            st = idx
        if "finished successfully" in line:
            end = idx
            break
        if "completed successfully" in line:
            end = idx
            break
    return lines[st+1:end]

def install_activate_deactivate(ctx, cmd):
    """
    Abort Situation:
    RP/0/RP0/CPU0:Deploy#install activate ncs6k-5.2.5.CSCuz65240-1.0.0

    Jun 02 20:19:31 Install operation 8 started by root:
      install activate pkg ncs6k-5.2.5.CSCuz65240-1.0.0
    Jun 02 20:19:31 Package list:
    Jun 02 20:19:31     ncs6k-5.2.5.CSCuz65240-1.0.0
    Jun 02 20:19:31     ncs6k-5.2.5.47I.CSCuy47880-0.0.4.i
    Jun 02 20:19:31     ncs6k-5.2.5.CSCux82987-1.0.0
    Jun 02 20:19:38 Install operation 8 aborted

    ------------------------------------------------------------------------------------------------------------
    Non-Reload Situation:

    RP/0/RP0/CPU0:Deploy#install deactivate ncs6k-5.2.5.CSCuz65240-1.0.0
    May 31 20:14:14 Install operation 3 started by root:
      install deactivate pkg ncs6k-5.2.5.CSCuz65240-1.0.0
    May 31 20:14:14 Package list:
    May 31 20:14:14     ncs6k-5.2.5.CSCuz65240-1.0.0
    May 31 20:14:20 Install operation will continue in the background (may or may not be displayed)

    <--- Time Lapses --->

    RP/0/RP0/CPU0:Deploy#May 31 20:15:10 Install operation 3 finished successfully

    ------------------------------------------------------------------------------------------------------------
    Reload Situation 1:

    RP/0/RP0/CPU0:Deploy#install activate ncs6k-5.2.5.CSCux82987-1.0.0
    May 31 20:17:08 Install operation 4 started by root:
      install activate pkg ncs6k-5.2.5.CSCux82987-1.0.0
    May 31 20:17:08 Package list:
    May 31 20:17:08     ncs6k-5.2.5.CSCux82987-1.0.0

    <--- Time Lapses --->

    This install operation will reboot the sdr, continue?
     [yes/no]:[yes] <Hit Enter>
    May 31 20:17:47 Install operation will continue in the background

    <--- Time Lapses --->

    RP/0/RP0/CPU0:Deploy#May 31 20:18:44 Install operation 4 finished successfully

    <--- Router Starts Reloading --->

    Connection closed by foreign host.

    Reload Situation 2:

    RP/0/RSP0/CPU0:ios#install activate id 25
    Jun 09 15:49:15 Install operation 27 started by root:
    install activate id 25
    Jun 09 15:49:15 Package list:
    Jun 09 15:49:15     asr9k-sysadmin-system-6.1.1.17-r61116I.CSCcv44444.x86_64
    Jun 09 15:49:15     asr9k-os-supp-64-3.1.0.1-r61116I.CSCxr90021.x86_64
    Jun 09 15:49:15     asr9k-base-64-4.0.0.2-r61116I.CSCxr90014.x86_64
    Jun 09 15:49:15     asr9k-sysadmin-topo-6.1.1.17-r61116I.CSCcv55555.x86_64

    This install operation will reload the sdr, continue?
    [yes/no]:[yes] <Hit Enter>
    Jun 09 15:49:26 Install operation will continue in the background
    RP/0/RSP0/CPU0:ios#

    <--- Time Lapses --->

    RP/0/RSP0/CPU0:ios#Jun 09 15:53:51 Install operation 27 finished successfully



    """
    global plugin_ctx
    plugin_ctx = ctx

    ABORTED = re.compile("aborted")

    # Seeing this message without the reboot prompt indicates a non-reload situation
    CONTINUE_IN_BACKGROUND = re.compile("Install operation will continue in the background")

    REBOOT_PROMPT = re.compile("This install operation will (?:reboot|reload) the sdr, continue")

    RUN_PROMPT = re.compile("#")

    NO_IMPACT = re.compile("NO IMPACT OPERATION")

    events = [CONTINUE_IN_BACKGROUND, REBOOT_PROMPT, ABORTED, NO_IMPACT, RUN_PROMPT]
    transitions = [
        (CONTINUE_IN_BACKGROUND, [0], -1, handle_non_reload_activate_deactivate, 100),
        (REBOOT_PROMPT, [0], -1, handle_reload_activate_deactivate, 100),
        (NO_IMPACT, [0], -1, no_impact_warning, 20),
        (RUN_PROMPT, [0], -1, handle_non_reload_activate_deactivate, 100),
        (ABORTED, [0], -1, handle_aborted, 100),
    ]

    if not ctx.run_fsm("activate or deactivate", cmd, events, transitions, timeout=100):
        ctx.error("Failed: {}".format(cmd))

def verify_pkgs(ctx):
    result = execute_cmd(ctx, "install verify packages")
    if result:
        return True
    ctx.error("install verification failed")
    return False

def send_admin_cmd(ctx, cmd):
    ctx.send("admin")
    output = ctx.send(cmd)
    ctx.send("exit")

    return output

def match_pattern(pattern, output):
    if pattern:
        regex = re.compile("%s" %"|".join(pattern))
        result_list = regex.findall(output)
        result = "^|^".join(result_list)
       
        if result:
            return True, "Pattern {} matched..!!!".format(result)
        else:
            return False, "Pattern {} not matched in {}!!!\n".format(pattern, output)

def next_level_processing(ctx):
    if ctx.nextlevel:
        ctx.info("Next level processing ")
        for cmds in ctx.nextlevel:
            shell = cmds.get("shell")
            cmd = cmds.get("command")
            pattern = cmds.get("pattern")
            if "Bash" in shell:
                 cmd = "run " + cmd
            if shell is "AdminBash":
                cmd_out = send_admin_cmd(ctx, cmd)
            else:
                cmd_out = ctx.send(cmd, timeout=100)
            if pattern:
                status, message = match_pattern(pattern, cmd_out)
                report_log(ctx, status, message) 

def checklist_in_cmd(ctx, cmd, pkg_list):
    """return the no of packages present in output of executing cmd"""
    """ it is caller's responsibility to swith to admin mode if required"""
    present = 0
    paragraph = ctx.send(cmd, timeout=60)
    for pkg in pkg_list:
        if pkg in paragraph:
            present += 1
    return present

def validate_is_active(ctx, pkg_list):
    return checklist_in_cmd(ctx, "show install active", pkg_list)

def validate_is_inactive(ctx, pkg_list):
    return checklist_in_cmd(ctx, "show install inactive", pkg_list)


def validate_is_committed(ctx, pkg_list):
    return checklist_in_cmd(ctx, "show install committed", pkg_list)

def commit_verify(ctx, pkg_list):
    try:
        result = execute_cmd(ctx, "install commit")
    except PluginError:
        pass
    time.sleep(60)
    return validate_is_committed(ctx, pkg_list)

def show_cmd(ctx, cmd):
    result = ctx.send(cmd, timeout=120)
    if not result:
        ctx.info("could not send show cmd")

def generic_show(ctx):
    show_cmd(ctx, "show install active")
    show_cmd(ctx, "show install inactive")
    show_cmd(ctx, "show install repository all")
    show_cmd(ctx, "show install superseded")

def get_sysadmin_op_id(output):
    global plugin_ctx
    result = re.search('Op Id (\d+)', output)
    if result:
        return result.group(1)

def handle_admin_non_reload(fsm_ctx):
    global plugin_ctx
    op_id = 0
    cmd_show_install_request = "show install request"
    while op_id <= 0:
        output = ""
        try:
            output = plugin_ctx.send(cmd_show_install_request, timeout=30)
        except plugin_ctx.CommandTimeoutError:
            pass
            continue
        op_id = get_sysadmin_op_id(output)
    try:
        watch_operation(plugin_ctx, op_id)
    except plugin_ctx.CommandTimeoutError:
        plugin_ctx.info("handle_admin_non_reload() got an exception when waiting for op to complete")
        pass
    return True

def handle_admin_reload(fsm_ctx):
    global plugin_ctx
    plugin_ctx.send("yes", timeout=30)
    cmd_show_install_request = "show install request"
    op_id = 0
    while op_id <= 0:
        output = plugin_ctx.send(cmd_show_install_request, timeout=30)
        op_id = get_sysadmin_op_id(output)
    try:
        watch_operation(plugin_ctx, op_id)
    except plugin_ctx.CommandTimeoutError:
        plugin_ctx.info("The device already started the reload")
        pass
    status = report_install_status(plugin_ctx, op_id)
    success = wait_for_reload(plugin_ctx)
    if not success:
        report_log(ctx, False, "Reload or boot failure")
        plugin_ctx.error("Reload or boot failure")
        return False

    if plugin_ctx.shell == "Admin":
        output = plugin_ctx.send("admin", timeout=30)
    return status

def handle_admin_reload_activate_deactivate(fsm_ctx):
    global plugin_ctx
    fsm_ctx.ctrl.sendline("yes", timeout=30)
    op_id = get_op_id(fsm_ctx.ctrl.before)
    return True


def handle_reload_cmd(fsm_ctx):
    """This handles a reload requiring a yes to start the op"""
    global plugin_ctx
    plugin_ctx.send("yes", timeout=30)
    nextlevel = plugin_ctx.nextlevel
    if nextlevel:
        next_level_processing(plugin_ctx)
    cmd_show_install_request = "show install request"
    op_id = 0
    while op_id <= 0:
        output = plugin_ctx.send(cmd_show_install_request, timeout=30)
        op_id = get_op_id(output)
    try:
        watch_operation(plugin_ctx, op_id)
    except plugin_ctx.CommandTimeoutError:
        plugin_ctx.info("The device already started the reload")
        pass
    status = report_install_status(plugin_ctx, op_id)
    success = wait_for_reload(plugin_ctx)
    if not success:
        report_log(ctx, False, "Reload or boot failure")
        plugin_ctx.error("Reload or boot failure")
        return False
    return success

def execute_cmd(ctx, cmd):
    """
    Abort Situation:
    RP/0/RP0/CPU0:Deploy#install activate ncs6k-5.2.5.CSCuz65240-1.0.0

    Jun 02 20:19:31 Install operation 8 started by root:
      install activate pkg ncs6k-5.2.5.CSCuz65240-1.0.0
    Jun 02 20:19:31 Package list:
    Jun 02 20:19:31     ncs6k-5.2.5.CSCuz65240-1.0.0
    Jun 02 20:19:31     ncs6k-5.2.5.47I.CSCuy47880-0.0.4.i
    Jun 02 20:19:31     ncs6k-5.2.5.CSCux82987-1.0.0
    Jun 02 20:19:38 Install operation 8 aborted

    ------------------------------------------------------------------------------------------------------------
    Non-Reload Situation:

    RP/0/RP0/CPU0:Deploy#install deactivate ncs6k-5.2.5.CSCuz65240-1.0.0
    May 31 20:14:14 Install operation 3 started by root:
      install deactivate pkg ncs6k-5.2.5.CSCuz65240-1.0.0
    May 31 20:14:14 Package list:
    May 31 20:14:14     ncs6k-5.2.5.CSCuz65240-1.0.0
    May 31 20:14:20 Install operation will continue in the background (may or may not be displayed)

    <--- Time Lapses --->

    RP/0/RP0/CPU0:Deploy#May 31 20:15:10 Install operation 3 finished successfully

    ------------------------------------------------------------------------------------------------------------
    Reload Situation 1:

    RP/0/RP0/CPU0:Deploy#install activate ncs6k-5.2.5.CSCux82987-1.0.0
    May 31 20:17:08 Install operation 4 started by root:
      install activate pkg ncs6k-5.2.5.CSCux82987-1.0.0
    May 31 20:17:08 Package list:
    May 31 20:17:08     ncs6k-5.2.5.CSCux82987-1.0.0

    <--- Time Lapses --->

    This install operation will reboot the sdr, continue?
     [yes/no]:[yes] <Hit Enter>
    May 31 20:17:47 Install operation will continue in the background

    <--- Time Lapses --->

    RP/0/RP0/CPU0:Deploy#May 31 20:18:44 Install operation 4 finished successfully

    <--- Router Starts Reloading --->

    Connection closed by foreign host.

    Reload Situation 2:

    RP/0/RSP0/CPU0:ios#install activate id 25
    Jun 09 15:49:15 Install operation 27 started by root:
    install activate id 25
    Jun 09 15:49:15 Package list:
    Jun 09 15:49:15     asr9k-sysadmin-system-6.1.1.17-r61116I.CSCcv44444.x86_64
    Jun 09 15:49:15     asr9k-os-supp-64-3.1.0.1-r61116I.CSCxr90021.x86_64
    Jun 09 15:49:15     asr9k-base-64-4.0.0.2-r61116I.CSCxr90014.x86_64
    Jun 09 15:49:15     asr9k-sysadmin-topo-6.1.1.17-r61116I.CSCcv55555.x86_64

    This install operation will reload the sdr, continue?
    [yes/no]:[yes] <Hit Enter>
    Jun 09 15:49:26 Install operation will continue in the background
    RP/0/RSP0/CPU0:ios#

    <--- Time Lapses --->

    RP/0/RSP0/CPU0:ios#Jun 09 15:53:51 Install operation 27 finished successfully



    """
    global plugin_ctx
    plugin_ctx = ctx

    ABORTED = re.compile("aborted")

    # Seeing this message without the reboot prompt indicates a non-reload situation
    CONTINUE_IN_BACKGROUND = re.compile("Install operation will continue in the background")
    CONTINUE_ASYNCHRONOUSLY = re.compile("will continue asynchronously")

    REBOOT_PROMPT = re.compile("This install operation will (?:reboot|reload) the sdr, continue")
    ADMIN_REBOOT_PROMPT = re.compile("Do you want to proceed")
    ISSU_PROMPT = re.compile("This install operation will start the issu")
    RUN_PROMPT = re.compile("#")
    HW_PROMPT = re.compile("hardware module ?")
    NO_IMPACT = re.compile("NO IMPACT OPERATION")
    DONE_PROMPT = re.compile("DONE")
    CONFIRM_PROMPT = re.compile("confirm")

    events = [CONTINUE_IN_BACKGROUND, CONTINUE_ASYNCHRONOUSLY, DONE_PROMPT, CONFIRM_PROMPT, ISSU_PROMPT, REBOOT_PROMPT, HW_PROMPT, ADMIN_REBOOT_PROMPT,ABORTED, NO_IMPACT, RUN_PROMPT]
    transitions = [
        (CONTINUE_IN_BACKGROUND, [0], -1, handle_non_reload_activate_deactivate, 100),
        (CONTINUE_ASYNCHRONOUSLY, [0], -1, handle_admin_non_reload, 100),
        (REBOOT_PROMPT, [0], -1, handle_reload_activate_deactivate, 100),
        (ADMIN_REBOOT_PROMPT, [0], -1, handle_admin_reload, 100),
        (ISSU_PROMPT, [0], -1, handle_reload_cmd, 20),
        (NO_IMPACT, [0], -1, no_impact_warning, 20),
        (RUN_PROMPT, [0], -1, handle_non_reload_activate_deactivate, 100),
        (HW_PROMPT, [0], -1, handle_hw_modify_cmd, 100),
        (CONFIRM_PROMPT, [0], -1, handle_confirm, 100),
        (DONE_PROMPT, [0], -1,handle_done, 100),
        (ABORTED, [0], -1, handle_aborted, 100),
    ]

    if not ctx.run_fsm("activate or deactivate", cmd, events, transitions, timeout=100):
        ctx.error("Failed: {}".format(cmd))
        return False
    return True

def wait_for_prompt(ctx):
    proceed = False
    while not proceed:
        ctx.info("checking if pending operation in progress")
	try:
            output = ctx.send(" show install request", timeout=30)
        except ctx.CommandTimeoutError:
            pass
        if "No install operation in progress" in output:
            proceed = True
        if not proceed:
            time.sleep(30)
    return

def process_save_data(ctx):
    ctx.info("Processing data to save")
    tc_id = ctx.tc_id - 1
    log_dir = ctx.log_directory
    tc_file = os.path.join(log_dir, 'tc.json')
    with open(tc_file) as fd_tc:
        data  = json.load(fd_tc)
    tc = data[tc_id]
    with open(tc_file) as fd_tc:
        tc_file_content  = fd_tc.read()
    if tc.get('save_data'):
        save_data = tc['save_data']
    else:
        return
    print save_data

    for to_save, to_replace in save_data.iteritems():
        to_save_value = getattr(ctx, to_save)
        ctx.info("Replace {} with value {}".format(to_replace , to_save_value))
        updated_content = tc_file_content.replace(to_replace, to_save_value)

    ctx.info("Writing {}".format(updated_content))

    with open(tc_file, 'w') as fd_tc:
        fd_tc.write(updated_content)


