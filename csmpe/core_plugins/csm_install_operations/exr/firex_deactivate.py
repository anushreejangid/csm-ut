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
from install import wait_for_prompt
from install import validate_is_inactive
#from time import sleep
import sys, traceback


class Plugin(CSMPlugin):
    """This plugin tests basic install operations on ios prompt."""
    name = "Install Deactivate Plugin"
    platforms = {'ASR9K', 'NCS1K', 'NCS5K', 'NCS5500', 'NCS6K', 'XRV9K'}
    phases = {'Activate'}
    os = {'eXR'}
    op_id = 0
    fsm_result = False

    def deactivate_id(self, pkg_id):
        if self.ctx.issu_mode:
            cmd = "install deactivate issu id {} ".format(pkg_id)
        else:
            cmd = "install deactivate id {} ".format(pkg_id)
        result = execute_cmd(self.ctx, cmd)
        return True

    def deactivate(self, pkgs):
        if self.ctx.issu_mode:
            cmd = "install deactivate issu {} ".format(pkgs)
        else:
            cmd = "install deactivate {} ".format(pkgs)
        result = execute_cmd(self.ctx, cmd)
        pkg_list = pkgs.split(' ')
        revert_to_ios = False
        if self.ctx.shell != "Admin":
            for pkg in pkg_list:
                if "admin" in pkg:
                    self.ctx.send("admin", timeout=30)
                    revert_to_ios = True
                    break
        result = validate_is_inactive(self.ctx, pkg_list)
	if revert_to_ios:
            self.ctx.send("exit", timeout=30)
        if result == len(pkg_list):
            self.ctx.info("Package(s) deactivated  Successfully")
        else:
            self.ctx.info("Failed to deactivate packages")
            return

    def run(self):
        check_ncs6k_release(self.ctx)

        packages = " ".join(self.ctx.software_packages)
        if hasattr(self.ctx, 'pkg_id'):
            pkg_id = " ".join(self.ctx.pkg_id)
#        if packages is None:
#            self.ctx.error("No package list provided")
#            return

        if self.ctx.shell == "Admin":
            self.ctx.send("admin", timeout=30)
	wait_for_prompt(self.ctx)
        try:
            if pkg_id:
	        self.deactivate_id(pkg_id)
            else:
	        self.deactivate(packages)
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
	    self.ctx.info(exc_traceback)
	    traceback.print_exception(exc_type, exc_value, exc_traceback,
                              limit=2, file=sys.stdout)
            traceback.print_exc(file=open("/tmp/errlog.txt","a"))
            self.ctx.info("deactivation failed")
            pass
            return False
        if self.ctx.shell == "Admin":
            self.ctx.send("exit", timeout=30)
        self.ctx.send("exit", timeout=30)
        return True
