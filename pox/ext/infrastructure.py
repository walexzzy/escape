# Copyright 2013 <Your Name Here>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Basic POX module for ESCAPE Infrastructure Layer

Initiate appropriate API class which emulate Co-Rm reference point

Follows POX module conventions
"""
from escape.infr.il_API import InfrastuctureLayerAPI
from pox.core import core
import pox.lib.util as poxutil

# Initial parameters
init_param = {}


def _start_layer (event):
  """
  Initiate and run Infrastructure module

  :param event: POX's going up event
  :type event: GoingUpEvent
  :return: None
  """
  # Instantiate the API class and register into pox.core only once
  InfrastuctureLayerAPI(**init_param)


@poxutil.eval_args
def launch (standalone=False):
  """
  Launch function called by POX core when core is up

  :param standalone: Run layer without dependency checking (optional)
  :type standalone: bool
  :return: None
  """
  global init_param
  init_param.update(locals())
  core.addListenerByName("UpEvent", _start_layer)
