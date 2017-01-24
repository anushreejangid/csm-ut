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
from install import generic_show



class Plugin(CSMPlugin):
    """This plugin tests install remove all operation."""
    name = "Install RemoveAll Plugin"
    platforms = {'ASR9K', 'NCS1K', 'NCS5K', 'NCS5500', 'NCS6K', 'XRV9K'}
    phases = {'Add'}
    os = {'eXR'}
    op_id = 0
    fsm_result = False

    def remove_all(self):
        cmd = "install remove inactive all "
        result = execute_cmd(self.ctx, cmd)
        if result:
            self.ctx.info("Package(s) remove Successfully")
        else:
            self.ctx.info("Failed to remove packages")
        self.ctx.info("Remove package(s) passed")
        self.ctx.post_status("Remove package(s) passed")
        generic_show(self.ctx)
        return result

    def run(self):
        check_ncs6k_release(self.ctx)

        if self.ctx.shell == "Admin":
            self.ctx.send("admin", timeout=30)
        if self.ctx.shell == "Admin":
            self.ctx.send("admin", timeout=30)
        wait_for_prompt(self.ctx)
        try:
            result = self.remove_all()
        except:
            result = False
            pass
        if self.ctx.shell == "Admin":
            self.ctx.send("exit", timeout=30)
        self.ctx.send("exit", timeout=30)
        return result
