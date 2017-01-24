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



class Plugin(CSMPlugin):
    """This plugin tests basic install operations on ios prompt."""
    name = "Install Prepare Plugin"
    platforms = {'ASR9K', 'NCS1K', 'NCS5K', 'NCS5500', 'NCS6K', 'XRV9K'}
    phases = {'Pre-Activate'}
    os = {'eXR'}
    op_id = 0
    fsm_result = False


    def prepare_id(self, pkg_id):
	self.ctx.info("pkg_id=")
	self.ctx.info(pkg_id)
        if self.ctx.issu_mode:
            cmd = "install prepare issu id {} ".format(pkg_id)
        else:
            cmd = "install prepare id {} ".format(pkg_id)
        result = execute_cmd(self.ctx, cmd)
        if result:
            self.ctx.post_status("Package(s) Prepared Successfully")
            process_save_data(self.ctx)
        else:
            self.ctx.info("Failed to prepared packages")
            return
        return result

    def prepare(self, pkgs):
        if self.ctx.issu_mode:
            cmd = "install prepare issu {} ".format(pkgs)
        else:
            cmd = "install prepare {} ".format(pkgs)
        result = execute_cmd(self.ctx, cmd)
        if result:
            self.ctx.post_status("Package(s) Prepared Successfully")
            process_save_data(self.ctx)
        else:
            self.ctx.post_status("Failed to prepare packages")
            return
        return result

    def run(self):
        check_ncs6k_release(self.ctx)
        self.ctx.info("Executing Prepare plugin")
        self.ctx.post_status("Executing Prepare plugin")
        packages = " ".join(self.ctx.software_packages)
        pkg_id = None
        
        if hasattr(self.ctx , 'pkg_id'):
            pkg_id = " ".join(self.ctx.pkg_id)

        if self.ctx.shell == "Admin":
            self.ctx.info("Switching to admin mode")
            self.ctx.send("admin", timeout=30)
        if self.ctx.shell == "Admin":
            self.ctx.send("admin", timeout=30)
	wait_for_prompt(self.ctx)

        if packages:
            self.ctx.info("Prepare packages specified explicitly")
            try:
                result = self.prepare(packages)
            except:
                self.ctx.info("prepare packages failed")
                pass
                return  False
        elif pkg_id:
            self.ctx.info("Prepare packages based on id {}".format(pkg_id))
            try:
                result = self.prepare_id(pkg_id)
            except:
                self.ctx.info("prepare package id failed")
                pass
                return False
        else:
            self.ctx.error("No package list provided")
            return False

        if self.ctx.shell == "Admin":
            self.ctx.send("exit", timeout=30)
        self.ctx.send("exit", timeout=30)
        return result
