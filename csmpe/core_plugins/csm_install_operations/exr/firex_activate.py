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
from install import check_ncs6k_release
from install import execute_cmd
from install import validate_is_active
#from time import sleep



class Plugin(CSMPlugin):
    """This plugin tests basic install operations on ios prompt."""
    name = "Install FirexActivate Plugin"
    platforms = {'ASR9K', 'NCS1K', 'NCS5K', 'NCS5500', 'NCS6K', 'XRV9K'}
    phases = {'Activate'}
    os = {'eXR'}
    op_id = 0
    fsm_result = False

    def activate(self):
        if self.ctx.issu_mode:
            result = execute_cmd(self.ctx, "install activate issu")
        else:
            result = execute_cmd(self.ctx, "install activate")
        if result:
            self.ctx.info("Package(s) activated Successfully")
        else:
            self.ctx.info("Failed to activated packages")
        return result

    def activate_id(self, pkg_id):
        if self.ctx.issu_mode:
            cmd = "install activate issu id {} ".format(pkg_id)
        else:
            cmd = "install activate id {} ".format(pkg_id)
        result = execute_cmd(self.ctx, cmd)
        return result

    def activate_pkgs(self, pkgs):
        if self.ctx.issu_mode:
            cmd = "install activate issu {} ".format(pkgs)
        else:
            cmd = "install activate {} ".format(pkgs)
        result = execute_cmd(self.ctx, cmd)
#        sleep(60)
        revert_to_ios = False
        if self.ctx.shell != "Admin":
            for pkg in pkg_list:
                if "admin" in pkg:
                    self.ctx.send("admin", timeout=30)
                    revert_to_ios = True
                    break
        result = validate_is_active(self.ctx, pkg_list)
        if revert_to_ios:
            self.ctx.send("exit", timeout=30)
        if result == len(pkg_list):
            self.ctx.info("Package(s) activated Successfully")
        else:
            self.ctx.info("Failed to activated packages")
            return False
        self.ctx.info("Activate package(s) passed")
        self.ctx.post_status("Activate package(s) passed")
        return True

    def run(self):
        check_ncs6k_release(self.ctx)

        packages = " ".join(self.ctx.software_packages)
        pkg_id = None
        if hasattr(self.ctx, 'pkg_id'):
            pkg_id = self.ctx.pkg_id
        if self.ctx.shell == "Admin":
            self.ctx.info("Switching to admin")
            self.ctx.send("admin", timeout=30)
        if packages:
	       result = self.activate_pkgs(packages)
        elif pkg_id:
	       result = self.activate_id(pkg_id)
        else:
	       result = self.activate()

        if self.ctx.shell == "Admin":
            self.ctx.info("Exiting from admin")
            self.ctx.send("exit", timeout=30)
        return result
