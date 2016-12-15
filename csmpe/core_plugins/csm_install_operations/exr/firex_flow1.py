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

from csmpe.plugins import CSMPlugin
from install import execute_cmd
from install import wait_for_prompt
from install import check_ncs6k_release
from install import get_pkgs
from install import validate_is_active
from install import validate_is_inactive
from install import commit_verify
from install import verify_pkgs
from install import generic_show
from time import sleep


class Plugin(CSMPlugin):
    """This plugin tests basic install operations on ios prompt."""
    name = "Install FirexFlow1 Plugin"
    platforms = {'ASR9K', 'NCS1K', 'NCS5K', 'NCS5500', 'NCS6K', 'XRV9K'}
    phases = {'Add'}
    os = {'eXR'}
    op_id = 0

    def add(self):
        result = False
        server_repository_url = self.ctx.server_repository_url
        packages = self.ctx.software_packages
        if self.ctx.family == 'NCS6K':
            s_packages = " ".join([package for package in packages
                                   if ('iso' in package or 'pkg' in package or 'smu' in package or 'tar' in package)])
        else:
            s_packages = " ".join([package for package in packages
                                   if ('rpm' in package or 'iso' in package or 'tar' in package)])

        has_tar = False
        if 'tar' in s_packages:
            has_tar = True
        if not s_packages:
            self.ctx.error("None of the selected package(s) has an acceptable file extension.")
        cmd = "install add source {} {} ".format(server_repository_url, s_packages)
        self.ctx.info("Execute cmd: {}".format(cmd))
        try:
            result = execute_cmd(self.ctx, cmd)
            self.ctx.info("execute_cmd() returned")
            self.ctx.info(result)
        except:
            self.ctx.info("got an exception")
            result = False
            pass
        if result:
            pkg_id = self.ctx.op_id
            if has_tar is True:
                self.ctx.operation_id = self.op_id
                self.ctx.info("The operation {} stored".format(self.op_id))
            self.ctx.info("Package(s) Added Successfully")
        else:
            self.ctx.info("Failed to add packages")
            self.ctx.error(result)
            return
        self.ctx.info("Add package(s) passed")
        self.ctx.post_status("Add package(s) passed")
        return get_pkgs(self.ctx, pkg_id)

    def remove(self, pkg_list):
        pkgs = ' '.join(pkg_list)
        cmd = "install remove  {} ".format(pkgs)
        result = execute_cmd(self.ctx, cmd)
        if result:
            self.ctx.info("Package(s) remove Successfully")
        else:
            self.ctx.info("Failed to remove packages")
            return
        self.ctx.info("Remove package(s) passed")
        self.ctx.post_status("Remove package(s) passed")
        generic_show(self.ctx)

    def prepare(self, pkg_list):
        pkgs = ' '.join(pkg_list)
        cmd = "install prepare {} ".format(pkgs)
        result = execute_cmd(self.ctx, cmd)
        if result:
            self.ctx.info("Package(s) Prepared Successfully")
        else:
            self.ctx.info("Failed to prepared packages")
            return
        self.ctx.send("show install prepare", timeout=30)

    def activate(self):
        result = execute_cmd(self.ctx, "install activate")
        if result:
            self.ctx.info("Package(s) activated Successfully")
        else:
            self.ctx.info("Failed to activated packages")
            return

    def activate_id(self, pkg_list):
        pkgs = ' '.join(pkg_list)
        cmd = "install activate {} ".format(pkgs)
        result = execute_cmd(self.ctx, cmd)
        sleep(60)
        result = validate_is_active(self.ctx, pkg_list)
        if result == len(pkg_list):
            self.ctx.info("Package(s) activated Successfully")
        else:
            self.ctx.info("Failed to activated packages")
            return
        self.ctx.info("Activate package(s) passed")
        self.ctx.post_status("Activate package(s) passed")
        if not verify_pkgs(self.ctx):
            return

    def deactivate(self, pkg_list):
        pkgs = ' '.join(pkg_list)
        cmd = "install deactivate {} ".format(pkgs)
        result = execute_cmd(self.ctx, cmd)
        sleep(60)
        result = validate_is_inactive(self.ctx, pkg_list)
        if result == len(pkg_list):
            self.ctx.info("Package(s) deactivated  Successfully")
        else:
            self.ctx.info("Failed to deactivate packages")
            return

    def clean(self):
        result = execute_cmd(self.ctx, "install prepare clean")

    def run(self):
        check_ncs6k_release(self.ctx)
        self.ctx.post_status("Install Add Plugin")
        server_repository_url = self.ctx.server_repository_url
        if server_repository_url is None:
            self.ctx.error("No repository provided")
            return

        packages = " ".join(self.ctx.software_packages)
        if packages is None:
            self.ctx.error("No package list provided")
            return

        if self.ctx.shell == "Admin":
            self.ctx.info("Switching to admin mode")
            self.ctx.send("admin", timeout=30)
	wait_for_prompt(self.ctx)
        pkg_list = self.add()
        self.ctx.info(pkg_list)
        num_pkgs = len(pkg_list)
        self.prepare(pkg_list)
        self.clean()
        self.prepare(pkg_list)
        self.activate()
        result = commit_verify(self.ctx, pkg_list)
        if result != num_pkgs:
            self.ctx.error("Failed to commit activated package")
        self.deactivate(pkg_list)
        result = commit_verify(self.ctx, pkg_list)
        if result:
            self.ctx.error("Failed to commit deactivated package")
        self.activate_id(pkg_list)
        result = commit_verify(self.ctx, pkg_list)
        if result != num_pkgs:
            self.ctx.error("Failed to commit activated package")
        self.deactivate(pkg_list)
        result = commit_verify(self.ctx, pkg_list)
        if result:
            self.ctx.error("Failed to commit deactivated package")
        self.remove(pkg_list)

        if self.ctx.shell == "Admin":
            self.ctx.info("Exiting from admin mode")
            self.ctx.send("exit", timeout=30)
        self.ctx.send("exit", timeout=30)
        if pkg_list:
            return True
        else:
            return False
