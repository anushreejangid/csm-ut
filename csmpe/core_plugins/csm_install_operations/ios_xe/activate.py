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


# from package_lib import SoftwarePackage
from time import time
from datetime import datetime
from csmpe.plugins import CSMPlugin
from install import expand_subpkgs
from install import install_activate_reload
from install import install_activate_write_memory
from install import install_activate_issu
from csmpe.core_plugins.csm_get_software_packages.ios_xe.plugin import get_package
from csmpe.core_plugins.csm_install_operations.utils import update_device_info_udi
from utils import remove_exist_image
from utils import xe_show_platform
from utils import install_add_remove


class Plugin(CSMPlugin):
    """This plugin Activates packages on the device."""
    name = "Install Activate Plugin"
    platforms = {'ASR900'}
    phases = {'Activate'}
    os = {'XE'}

    def run(self):
        """
        Performs install activate operation
        """

        rsp_count = int(self.ctx.load_data('xe_rsp_count')[0])
        pkg = self.ctx.load_data('xe_activate_pkg')[0]
        mode = self.ctx.load_data('xe_boot_mode')[0]
        folder = self.ctx.load_data('xe_install_folder')[0]

        self.ctx.info("Activate number of RSP = {}".format(rsp_count))
        self.ctx.info("Activate package = {}".format(pkg))
        self.ctx.info("Activate package mode = {}".format(mode))
        self.ctx.info("Install folder = {}".format(folder))

        self.ctx.info("Activate package(s) pending")
        self.ctx.post_status("Activate Package(s) Pending")

        prompt = self.ctx._connection.hostname

        # issu: need to copy the consolidated image to the installed folder
        if mode == 'issu':
            cmd = 'copy bootflash:' + pkg + ' ' + folder + '/' + pkg
            install_add_remove(self.ctx, cmd)
            package = 'bootflash:' + pkg
            remove_exist_image(self.ctx, package)

        # subpackage: need to expand the consolidated image to the installed folder
        if mode == 'subpackage':
            result = expand_subpkgs(self.ctx, rsp_count, folder, pkg)
            if not result:
                self.ctx.error("Error in extracting sub-images from the consolidated "
                               "image {}".format(pkg))
                return

        # configurations
        cmd = "configure terminal"
        self.ctx.send(cmd, wait_for_string=prompt)
        cmd = "config-register 0x2102"
        self.ctx.send(cmd, wait_for_string=prompt)

        if mode == 'issu':
            cmd = 'redundancy'
            self.ctx.send(cmd, wait_for_string=prompt)
            cmd = 'mode sso'
            self.ctx.send(cmd, wait_for_string=prompt)
        else:
            cmd = "no boot system"
            self.ctx.send(cmd, wait_for_string=prompt)
            if mode == 'consolidated':
                cmd = "boot system bootflash:" + pkg
            else:
                cmd = 'boot system ' + folder + '/packages.conf'
            self.ctx.send(cmd, wait_for_string=prompt)

        self.ctx.send('end', wait_for_string=prompt)

        cmd = "write memory"
        install_activate_write_memory(self.ctx, cmd, self.ctx._connection.hostname)
        # self.ctx.send(cmd, timeout=300, wait_for_string=prompt)

        # Start activation
        if mode == 'issu':
            cmd = 'request platform software package install node file ' + \
                  folder + '/' + pkg + ' interface-module-delay 160'
            install_activate_issu(self.ctx, cmd)

            # Remove all-in-one image from the installed folder
            package = folder + '/' + pkg
            remove_exist_image(self.ctx, package)
            package = 'stby-' + package
            remove_exist_image(self.ctx, package)

            # Remove the all-in-one image from stby-bootflash:
            package = 'stby-bootflash:' + pkg
            remove_exist_image(self.ctx, package)
        else:
            install_activate_reload(self.ctx)

        self.ctx.info("Activate package done")

        # Refresh package information
        get_package(self.ctx)

        update_device_info_udi(self.ctx)

        # Verify the version after activation
        if self.ctx._connection.os_version not in pkg:
            self.ctx.error('The post-activate OS Version: '
                           '{}'.format(self.ctx._connection.os_version))

        # Verify the status of RP and SIP
        previous_data, timestamp = self.ctx.load_data('xe_show_platform')
        self.ctx.info("Pre-Activate data collected on {}".format(
            datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')))
        if timestamp < time() - (60 * 60 * 2):  # two hours
            self.ctx.warning("Pre-Activate phase 'show platform' "
                             "data older than 2 hours")

        current_data = xe_show_platform(self.ctx)
        if not current_data:
            self.ctx.error("The CLI 'show platform' is not able to determine the status of RP and SIP ")
            return

        for Slot, Status in previous_data.items():
            Type = Status[0]
            previous_state = Status[1]
            current_state = current_data[Slot][1]
            if previous_state != current_state:
                if previous_state == 'ok, active' and current_state == 'ok, standby' \
                        or previous_state == 'ok, standby' and current_state == 'ok, active':
                    continue
                self.ctx.warning("Slot {} Type {} state changes after Activation".format(Slot, Type))
                self.ctx.warning("\t Pre-Activate State = {} vs. Post-Activate State = "
                                 "{}".format(previous_state, current_state))
            if 'ok' not in current_state:
                self.ctx.warning("Slot {} Type {} is not in 'ok' state after "
                                 "activation".format(Slot, Type))

        self.ctx.info("The status of RP and SIP has been verified. Please check any warnings in plugins.log")