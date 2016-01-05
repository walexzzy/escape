# Copyright 2015 Janos Czentye, Raphael Vicente Rosa
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
Contains helper classes for conversion between different NF-FG representations.
"""
import logging
import sys
import xml.etree.ElementTree as ET

try:
  # Import for ESCAPEv2
  from escape.util.nffg import AbstractNFFG, NFFG
except ImportError:
  import os, inspect

  sys.path.insert(0, os.path.join(os.path.abspath(
     os.path.join(os.path.dirname(__file__), "../../../..")),
     "pox/ext/escape/util/"))
  # Import for standalone running
  from nffg import AbstractNFFG, NFFG

try:
  # Import for ESCAPEv2
  import virtualizer3 as virt3
  from virtualizer3 import Flowentry
except ImportError:
  import os, inspect

  sys.path.insert(0, os.path.join(os.path.abspath(
     os.path.join(os.path.dirname(__file__), "../../../..")),
     "unify_virtualizer"))
  # Import for standalone running
  import virtualizer3 as virt3
  from virtualizer3 import Flowentry


class NFFGConverter(object):
  """
  Convert different representation of NFFG in both ways.
  """

  TYPE_VIRTUALIZER_PORT_ABSTRACT = "port-abstract"
  TYPE_VIRTUALIZER_PORT_SAP = "port-sap"

  def __init__ (self, domain, logger=None):
    self.domain = domain
    self.log = logger if logger is not None else logging.getLogger(__name__)

  def parse_from_Virtualizer3 (self, xml_data):
    """
    Convert Virtualizer3-based XML str --> NFFGModel based NFFG object

    :param xml_data: XML plain data formatted with Virtualizer
    :type: xml_data: str
    :return: created NF-FG
    :rtype: :any:`NFFG`
    """
    try:
      self.log.debug("Converting data to graph-based NFFG structure...")
      # Parse given str to XML structure
      tree = ET.ElementTree(ET.fromstring(xml_data))
      # Parse Virtualizer structure
      self.log.debug("Parsing XML data to Virtualizer format...")
      virtualizer = virt3.Virtualizer().parse(root=tree.getroot())
    except ET.ParseError as e:
      raise RuntimeError('ParseError: %s' % e.message)

    # Get NFFG init params
    nffg_id = virtualizer.id.get_value() if virtualizer.id.is_initialized() \
      else "NFFG-%s" % self.domain
    nffg_name = virtualizer.name.get_value() if \
      virtualizer.name.is_initialized() else nffg_id

    self.log.debug("Construct NFFG based on Virtualizer(id=%s, name=%s)" % (
      nffg_id, nffg_name))
    # Create NFFG
    nffg = NFFG(id=nffg_id, name=nffg_name)

    # Iterate over virtualizer/nodes --> node = Infra
    for inode in virtualizer.nodes:
      # Node params
      _id = inode.id.get_value()
      _name = inode.name.get_value() if inode.name.is_initialized() else \
        "name-" + _id
      # Set domain as the domain of the Converter
      _domain = self.domain
      _infra_type = inode.type.get_value()
      # Node-resources params
      if inode.resources.is_initialized():
        # Remove units and store the value only
        _cpu = inode.resources.cpu.get_as_text().split(' ')[0]
        _mem = inode.resources.mem.get_as_text().split(' ')[0]
        _storage = inode.resources.storage.get_as_text().split(' ')[0]
        try:
          _cpu = int(_cpu)
          _mem = int(_mem)
          _storage = int(_storage)
        except ValueError:
          self.log.warning("Resource value(s) are not valid numbers!")
      else:
        # _cpu = sys.maxint
        # _mem = sys.maxint
        # _storage = sys.maxint
        _cpu = None
        _mem = None
        _storage = None

      # Iterate over links to summarize bw value for infra node
      # Default value: None
      _bandwidth = [
        float(link.resources.bandwidth.get_value()) for link in inode.links if
        link.resources.is_initialized() and
        link.resources.bandwidth.is_initialized()]
      _bandwidth = min(_bandwidth) if _bandwidth else None
      # Iterate over links to summarize delay value for infra node
      # Default value: None
      _delay = [
        float(link.resources.delay.get_value()) for link in inode.links if
        link.resources.is_initialized() and
        link.resources.delay.is_initialized()]
      _delay = max(_delay) if _delay else None

      # Add Infra Node
      infra = nffg.add_infra(id=_id, name=_name, domain=_domain,
                             infra_type=_infra_type, cpu=_cpu, mem=_mem,
                             storage=_storage, delay=_delay,
                             bandwidth=_bandwidth)
      self.log.debug("Create infra: %s" % infra)

      # Add supported types shrinked from the supported NF list
      for sup_nf in inode.capabilities.supported_NFs:
        infra.add_supported_type(sup_nf.type.get_value())

      # Add ports to Infra Node
      for port in inode.ports:
        # If it is a port connected to a SAP
        if port.port_type.get_value() == self.TYPE_VIRTUALIZER_PORT_SAP:
          # If inter-domain SAP
          if port.sap.is_initialized():
            # Use unique SAP tag as the id of the SAP
            s_id = port.sap.get_value()
          # Regular SAP
          else:
            # Use port name as the SAP.id if it is set else generate one
            s_id = port.name.get_value() if port.name.is_initialized() else \
              "SAP%s" % len([s for s in nffg.saps])
          try:
            sap_port_id = int(port.id.get_value())
          except ValueError:
            sap_port_id = port.id.get_value()
          s_name = port.name.get_value() if port.name.is_initialized() else \
            "name-" + s_id

          # Create SAP and Add port to SAP
          # SAP default port: sap-type port number
          sap = nffg.add_sap(id=s_id, name=s_name)
          self.log.debug("Create SAP: %s" % sap)
          sap_port = sap.add_port(id=sap_port_id)
          # Add port properties as metadata to SAP port
          if port.name.is_initialized():
            sap_port.add_property("name:%s" % port.name.get_value())
          if port.sap.is_initialized():
            sap_port.add_property("sap:%s" % port.sap.get_value())
            # sap_port.add_property("type:%s" % port.sap.get_value())
            self.log.debug("Add SAP port: %s" % sap_port)

          # Create and add the opposite Infra port
          try:
            infra_port_id = int(port.id.get_value())
          except ValueError:
            infra_port_id = port.id.get_value()
          infra_port = infra.add_port(id=infra_port_id)
          # Add port properties as metadata to Infra port too
          infra_port.add_property("name:%s" % port.name.get_value())
          # infra_port.add_property("port_type:%s" % port.port_type.get_value())
          if port.sap.is_initialized():
            infra_port.add_property("sap:%s" % port.sap.get_value())

          # Add infra port capabilities
          if port.capability.is_initialized():
            infra_port.add_property(
               "capability:%s" % port.capability.get_value())
          self.log.debug("Add Infra port: %s" % infra_port)

          # Add connection between infra - SAP
          # SAP-Infra is static link --> create link for both direction
          l1, l2 = nffg.add_undirected_link(port1=sap_port, port2=infra_port,
                                            delay=_delay, bandwidth=_bandwidth)
          self.log.debug("Add connection: %s" % l1)
          self.log.debug("Add connection: %s" % l2)

        # If it is not SAP port and probably connected to another infra
        elif port.port_type.get_value() == self.TYPE_VIRTUALIZER_PORT_ABSTRACT:
          # Add default port
          try:
            infra_port_id = int(port.id.get_value())
          except ValueError:
            infra_port_id = port.id.get_value()

          # Add port properties as metadata to Infra port
          infra_port = infra.add_port(id=infra_port_id)
          if port.name.is_initialized():
            infra_port.add_property("name:%s" % port.name.get_value())
          # If sap is set and port_type is port-abstract -> this port
          # connected  to an inter-domain SAP before -> save this metadata
          if port.sap.is_initialized():
            infra_port.add_property("sap:%s" % port.sap.get_value())
          if port.capability.is_initialized():
            infra_port.add_property(
               "capability:%s" % port.capability.get_value())
          self.log.debug("Add Infra port: %s" % infra_port)
        else:
          raise RuntimeError(
             "Unsupported port type: %s" % port.port_type.get_value())

      # Create NF instances
      for nf_inst in inode.NF_instances:
        # Get NF params
        nf_id = nf_inst.id.get_as_text()
        nf_name = nf_inst.name.get_as_text() if nf_inst.name.is_initialized() \
          else nf_id
        nf_ftype = nf_inst.type.get_as_text() if nf_inst.type.is_initialized() \
          else None
        nf_dtype = None
        nf_cpu = nf_inst.resources.cpu.get_as_text()
        nf_mem = nf_inst.resources.mem.get_as_text()
        nf_storage = nf_inst.resources.storage.get_as_text()
        try:
          nf_cpu = int(nf_cpu) if nf_cpu is not None else None
          nf_mem = int(nf_mem) if nf_cpu is not None else None
          nf_storage = int(nf_storage) if nf_cpu is not None else None
        except ValueError:
          pass
        nf_cpu = nf_cpu
        nf_mem = nf_mem
        nf_storage = nf_storage

        # Create NodeNF
        nf = nffg.add_nf(id=nf_id, name=nf_name, func_type=nf_ftype,
                         dep_type=nf_dtype, cpu=nf_cpu, mem=nf_mem,
                         storage=nf_storage, delay=_delay, bandwidth=_bandwidth)
        self.log.debug("Create NF: %s" % nf)

        # Create NF ports
        for nf_inst_port in nf_inst.ports:

          # Create and Add port
          nf_port = nf.add_port(id=nf_inst_port.id.get_as_text())

          # Add port properties as metadata to NF port
          if nf_inst_port.capability.is_initialized():
            nf_port.add_property(
               "capability:%s" % nf_inst_port.capability.get_as_text())
          if nf_inst_port.name.is_initialized():
            nf_port.add_property("name:%s" % nf_inst_port.name.get_as_text())
          if nf_inst_port.port_type.is_initialized():
            nf_port.add_property(
               "port_type:%s" % nf_inst_port.port_type.get_as_text())
          self.log.debug("Add NF port: %s" % nf_port)

          # Add connection between Infra - NF
          # Get the smallest available port for the Infra Node
          next_port = max(max({p.id for p in infra.ports}) + 1,
                          len(infra.ports))
          # Add Infra-side port
          infra_port = infra.add_port(id=next_port)
          self.log.debug("Add Infra port: %s" % infra_port)

          # NF-Infra is dynamic link --> create special undirected link
          l1, l2 = nffg.add_undirected_link(port1=nf_port, port2=infra_port,
                                            dynamic=True, delay=_delay,
                                            bandwidth=_bandwidth)
          self.log.debug("Add connection: %s" % l1)
          self.log.debug("Add connection: %s" % l2)
          # TODO - add flowrule parsing
    # Add links connecting infras
    for link in virtualizer.links:
      src_port = link.src.get_target().id.get_value()
      src_node = link.src.get_target().get_parent().get_parent().id.get_value()
      dst_port = link.dst.get_target().id.get_value()
      dst_node = link.dst.get_target().get_parent().get_parent().id.get_value()
      try:
        src_port = int(src_port)
        dst_port = int(dst_port)
      except ValueError as e:
        self.log.warning("Port id is not a valid number: %s" % e)
      params = dict()
      params['p1p2id'] = link.id.get_value()
      params['p2p1id'] = link.id.get_as_text() + "-back"
      if link.resources.is_initialized():
        params['delay'] = float(link.resources.delay.get_value()) if \
          link.resources.delay.is_initialized() else None
        params['bandwidth'] = float(link.resources.bandwidth.get_value()) if \
          link.resources.bandwidth.is_initialized() else None
      nffg.add_undirected_link(
         port1=nffg[src_node].ports[src_port],
         port2=nffg[dst_node].ports[dst_port],
         **params
      )

    return nffg, virtualizer

  def dump_to_Virtualizer3 (self, nffg):
    """
    Convert given :any:`NFFG` to Virtualizer3 format.

    :param nffg: topology description
    :type nffg: :any:`NFFG`
    :return: topology in Virtualizer3 format
    """
    self.log.debug("Converting data to XML-based Virtualizer structure...")
    # Create empty Virtualizer
    virt = virt3.Virtualizer(id=str(nffg.id), name=str(nffg.name))
    self.log.debug("Creating Virtualizer based on %s" % nffg)

    for infra in nffg.infras:
      self.log.debug("Converting %s" % infra)
      # Create infra node with basic params - nodes/node/{id,name,type}
      infra_node = virt3.Infra_node(id=str(infra.id), name=str(infra.name),
                                    type=str(infra.infra_type))

      # Add resources nodes/node/resources
      if infra.resources.cpu:
        infra_node.resources.cpu.set_value(str(infra.resources.cpu))
      if infra.resources.mem:
        infra_node.resources.mem.set_value(str(infra.resources.mem))
      if infra.resources.storage:
        infra_node.resources.storage.set_value(str(infra.resources.storage))

      # Add ports to infra
      for port in infra.ports:
        try:
          if not int(port.id) < 65536:
            # Dynamic port connected to a VNF - skip
            continue
        except ValueError:
          # port is is not a port number - best thing to leave it
          pass
        _port = virt3.Port(id=str(port.id))
        # Detect Port properties
        if port.get_property("name"):
          _port.name.set_value(port.get_property("name"))
        if port.get_property("capability"):
          _port.capability.set_value(port.get_property("capability"))
        # If SAP property is exist: this port connected to a SAP
        if port.get_property("sap"):
          _port.sap.set_value(port.get_property("sap"))
        # Set default port-type to port-abstract
        # during SAP detection the SAP<->Node port-type will be overridden
        _port.port_type.set_value(self.TYPE_VIRTUALIZER_PORT_ABSTRACT)
        # port_type: port-abstract & sap: -    -->  regular port
        # port_type: port-abstract & sap: <SAP...>    -->  was connected to
        # an inter-domain port - set this data in Virtualizer
        infra_node.ports.add(_port)

      # Add minimalistic Node for supported NFs based on supported list of NFFG
      for sup in infra.supported:
        infra_node.capabilities.supported_NFs.add(
           virt3.Node(id=str(sup), type=str(sup)))

      # Add infra to virtualizer
      virt.nodes.add(infra_node)

      if infra.resources.delay is not None or infra.resources.bandwidth is \
         not None:
        # Define full-mesh intra-links for nodes to set bandwidth and delay
        # values
        from itertools import combinations
        # Detect the number of ports
        port_num = len(infra_node.ports.port._data)
        if port_num > 1:
          # There are valid port-pairs
          for port_pair in combinations(
             (p.id.get_value() for p in infra_node.ports), 2):
            # Create link
            _link = virt3.Link(
               src=infra_node.ports[port_pair[0]],
               dst=infra_node.ports[port_pair[1]],
               resources=virt3.Link_resource(
                  delay=str(
                     infra.resources.delay) if infra.resources.delay else None,
                  bandwidth=str(
                     infra.resources.bandwidth) if infra.resources.bandwidth
                  else None
               )
            )
            # Call bind to resolve src,dst references to workaround a bug
            _link.bind()
            infra_node.links.add(_link)
        elif port_num == 1:
          # Only one port in infra - create loop-edge
          _src = _dst = iter(infra_node.ports).next()
          _link = virt3.Link(
             src=_src,
             dst=_dst,
             resources=virt3.Link_resource(
                delay=str(
                   infra.resources.delay) if infra.resources.delay else None,
                bandwidth=str(
                   infra.resources.bandwidth) if infra.resources.bandwidth
                else None
             )
          )  # Call bind to resolve src,dst references to workaround a bug
          _link.bind()
          infra_node.links.add(_link)
        else:
          # No port in Infra - unusual but acceptable
          self.log.warning(
             "No port has been detected in %s. Can not store internal "
             "bandwidth/delay value!" % infra)

    # Rewrite SAP - Node ports to add SAP to Virtualizer
    for sap in nffg.saps:
      for s, n, link in nffg.network.edges_iter([sap.id], data=True):
        # Rewrite port-type to port-sap
        virt.nodes[n].ports[str(link.dst.id)].port_type.set_value(
           self.TYPE_VIRTUALIZER_PORT_SAP)
        # Add SAP.name as name to port or use sap.id
        if link.src.get_property("name"):
          _name = link.src.get_property("name")
        else:
          _name = str(sap.name) if sap.name else str(sap.id)
        virt.nodes[n].ports[str(link.dst.id)].name.set_value(_name)
        self.log.debug(
           "Convert SAP to port: %s in infra: %s" % (link.dst.id, n))
        # Check if the SAP is an inter-domain SAP
        if nffg[s].domain is not None:
          virt.nodes[n].ports[str(link.dst.id)].sap.set_value(s)
          self.log.debug(
             "Convert inter-domain SAP to port: %s in infra: %s" % (
               link.dst.id, n))

    # Add link to Virtualizer
    for link in nffg.links:
      # SAP - Infra links are not stored in Virtualizer format
      # Skip backward link conversion <-- Virtualizer links are bidirectional
      if link.src.node.type == NFFG.TYPE_SAP or \
            link.dst.node.type == NFFG.TYPE_SAP or link.backward is True:
        continue
      self.log.debug("Add link: Node: %s, port: %s <--> Node: %s, port: %s" % (
        link.src.node.id, link.src.id, link.dst.node.id, link.dst.id))
      _link = virt3.Link(
         id=str(link.id),
         src=virt.nodes[str(link.src.node.id)].ports[str(link.src.id)],
         dst=virt.nodes[str(link.dst.node.id)].ports[str(link.dst.id)],
         resources=virt3.Link_resource(
            delay=str(link.delay),
            bandwidth=str(link.bandwidth)
         )
      )
      # Call bind to resolve src,dst references to workaround a bug
      _link.bind()
      virt.links.add(_link)

    # explicitly call bind to resolve relative paths for safety reason
    virt.bind()
    # Return with created Virtualizer
    return virt

    # # Clear unnecessary links

    #   nffg.clear_links(NFFG.TYPE_LINK_REQUIREMENT)
    #   nffg.clear_links(NFFG.TYPE_LINK_SG)
    #   # nffg.clear_links(NFFG.TYPE_LINK_DYNAMIC)
    #   # If virtualizer is not given create the infras,ports,SAPs first then
    #   # insert the initiated NFs and flowrules, supported NFs skipped!
    #     # Add bare Infra node entities
    #     for infra in nffg.infras:
    #     # Add Nfs to the Infra node
    #     for infra in nffg.infras:
    #       # for nf in nffg.running_nfs(infra.id):
    #       for nf_link in {link for u, v, link in
    #                       nffg.network.out_edges_iter((infra.id,),
    # data=True) if
    #                       link.dst.node.type == NFFG.TYPE_NF}:
    #         nf = nf_link.dst.node
    #         try:
    #           nf_inst = virtualizer.nodes[infra.id].NF_instances[nf.id]
    #         except KeyError:
    #           # Create resource to NF - NF_instances/node/resources
    #           cpu = str(nf.resources.cpu) if nf.resources.cpu else None
    #           mem = str(nf.resources.mem) if nf.resources.mem else None
    #           storage = str(
    #             nf.resources.storage) if nf.resources.storage else None
    #           res = virt3.NodeResources(cpu=cpu, mem=mem, storage=storage)
    #           # Create NF with resources - NF_instances/node
    #           nf_inst = virt3.Node(id=str(nf.id),
    #                                name=str(nf.name) if nf.name else None,
    #                                type=str(
    #                                  nf.functional_type) if
    # nf.functional_type
    #                                else None, resources=res)
    #           # Add NF to the Infra node
    #           virtualizer.nodes[infra.id].NF_instances.add(nf_inst)
    #         # Get port name
    #         port_name = "port" + str(nf_link.dst.id)
    #         for property in nf_link.dst.properties:
    #           if property.startswith('name'):
    #             port_name = property.split(':')[1]
    #             break
    #         # Create Port object
    #         nf_port = virt3.Port(id=str(nf_link.dst.id), name=str(
    # port_name),
    #                              port_type="port-abstract")
    #         # Add port to NF
    #         nf_inst.ports.add(nf_port)
    #     # TODO - add static links???
    #     # FIXME - this is a little bit of hack
    #     # FIXME - SAP ports created again -> override good sap port
    #     # for infra in nffg.infras:
    #     #   for port in infra.ports:
    #     #     # bigger than 65535 --> virtual port which is an object id,
    # not phy
    #     #     if len(str(port.id)) > 5:
    #     #       continue
    #     #     # if the port not exist in the virtualizer
    #     #     if str(port.id) not in virtualizer.nodes[
    #     #       infra.id].ports.port.getKeys():
    #     #       port_name = "port" + str(port.id)
    #     #       for property in port.properties:
    #     #         if property.startswith('name'):
    #     #           port_name = property.split(':')[1]
    #     #         break
    #     #       virtualizer.nodes[infra.id].ports.add(
    #     #         virt3.Port(id=str(port.id), name=port_name,
    #     #                    port_type="port-abstract"), )
    #     #       # print virtualizer
    #     # TODO - add flowrule
    #     # Add flowrules
    #     cntr = 0
    #     for infra in nffg.infras:
    #       for port in infra.ports:
    #         for flowrule in port.flowrules:
    #           # print flowrule
    #           # Get id
    #           f_id = str(cntr)
    #           cntr += 1
    #           # Get priority
    #           priority = str('100')
    #           # Get in port
    #           fr = flowrule.match.split(";")
    #           if fr[0].split('=')[0] != "in_port":
    #             raise RuntimeError(
    #               "Wrong flowrule format: missing in in_port from match")
    #           in_port = str(port.id)
    #           # in_port = fr[0].split('=')[1]
    #           try:
    #             # Flowrule in_port is a phy port in Infra Node
    #             in_port = virtualizer.nodes[infra.id].ports[in_port]
    #           except KeyError:
    #             # in_port is a dynamic port --> search for connected NF's
    #  port
    #             from pprint import pprint
    #             pprint(nffg.network.__dict__)
    #             # in_port, p_nf = [(str(l.dst.id), l.dst.node.id) for u, v,
    #  l in
    #             #                  nffg.network.out_edges_iter((infra.id,),
    #             #                                              data=True) if
    #             #                  str(l.src.id) == str(in_port)][0]
    #             print virtualizer
    #             for u, v, l in nffg.network.edges(data=True):
    #               print u, v, l
    #               if l.src.id == port.id:
    #                 print l.dst.id
    #
    #             # in_port, p_nf = [(str(l.dst.id), l.dst.node.id) for u, v,
    #  l in
    #             #                  nffg.network.out_edges_iter((infra.id,),
    #             #                                              data=True) if
    #             #                  str(l.src.id) == str(in_port)][0]
    #
    #             in_port = virtualizer.nodes[infra.id].NF_instances[
    # p_nf].ports[
    #               in_port]
    #           # Get match
    #           match = None
    #           if len(fr) > 1:
    #             if fr[1].split('=')[0] == "TAG":
    #               vlan = int(fr[1].split('=')[1].split('-')[-1])
    #               if self.domain == NFFG.DOMAIN_OS:
    #                 match = r"dl_vlan=%s" % format(vlan, '#06x')
    #               elif self.domain == NFFG.DOMAIN_UN:
    #                 match = u"<vlan_id>%s<vlan_id>" % vlan
    #             elif fr[1].split('=')[0] == "UNTAG":
    #               if self.domain == NFFG.DOMAIN_OS:
    #                 match = r"strip_vlan"
    #               elif self.domain == NFFG.DOMAIN_UN:
    #                 match = u"<vlan><pop/></vlan>"
    #           # Get out port
    #           fr = flowrule.action.split(';')
    #           if fr[0].split('=')[0] != "output":
    #             raise RuntimeError(
    #               "Wrong flowrule format: missing output from action")
    #           out_port = fr[0].split('=')[1]
    #           try:
    #             # Flowrule in_port is a phy port in Infra Node
    #             out_port = virtualizer.nodes[infra.id].ports[out_port]
    #           except KeyError:
    #             # out_port is a dynamic port --> search for connected NF's
    # port
    #             out_port, p_nf = [(str(l.dst.id), l.dst.node.id) for u, v,
    # l in
    #                               nffg.network.out_edges_iter((infra.id,),
    #                                                           data=True) if
    #                               str(l.src.id) == out_port][0]
    #             out_port = virtualizer.nodes[infra.id].NF_instances[
    # p_nf].ports[
    #               out_port]
    #           # Get action
    #           action = None
    #           if len(fr) > 1:
    #             if fr[1].split('=')[0] == "TAG":
    #               vlan = int(fr[1].split('=')[1].split('-')[-1])
    #               if self.domain == NFFG.DOMAIN_OS:
    #                 action = r"mod_vlan_vid:%s" % format(vlan, '#06x')
    #               elif self.domain == NFFG.DOMAIN_UN:
    #                 action = u"<vlan_id>%s<vlan_id>" % vlan
    #             elif fr[1].split('=')[0] == "UNTAG":
    #               if self.domain == NFFG.DOMAIN_OS:
    #                 action = r"strip_vlan"
    #               elif self.domain == NFFG.DOMAIN_UN:
    #                 action = u"<vlan><pop/></vlan>"
    #           # print out_port
    #           virtualizer.nodes[infra.id].flowtable.add(
    #             Flowentry(id=f_id, priority=priority, port=in_port,
    # match=match,
    #                       action=action, out=out_port))
    #   return virtualizer, nffg

  @staticmethod
  def unescape_output_hack (data):
    return data.replace("&lt;", "<").replace("&gt;", ">")

  def adapt_mapping_into_Virtualizer (self, virtualizer, nffg):
    """
    Install NFFG part or complete NFFG into given Virtualizer.

    :param virtualizer: Virtualizer object based on ETH's XML/Yang version.
    :param nffg: splitted NFFG (not necessarily in valid syntax)
    :return: modified Virtualizer object
    """
    self.log.debug(
       "Adapt modification from %s into Virtualizer(id=%s, name=%s)" % (
         nffg, virtualizer.id.get_as_text(), virtualizer.name.get_as_text()))
    self.log.debug("Check up on mapped NFs...")
    # Check every infra Node
    for infra in nffg.infras:
      # Cache discovered NF to avoid multiple detection of NF which has more
      # than one port
      discovered_nfs = []
      # Check in infra is exist in the Virtualizer
      if str(infra.id) not in virtualizer.nodes.node.keys():
        self.log.warning(
           "InfraNode: %s is not in the Virtualizer! Skip related "
           "initiations..." % infra)
        continue
      # Check every outgoing edge
      for u, v, link in nffg.network.out_edges_iter([infra.id], data=True):
        # Observe only the NF neighbours
        if link.dst.node.type != NFFG.TYPE_NF:
          continue
        nf = link.dst.node
        # Skip already detected NFs
        if nf.id in discovered_nfs:
          continue
        # Check if the NF is exist in the InfraNode
        if str(v) not in virtualizer.nodes[str(u)].NF_instances.node.keys():
          self.log.debug("Found uninitiated NF: %s in mapped NFFG" % nf)
          # Convert Resources to str for XML conversion
          v_nf_cpu = str(
             nf.resources.cpu) if nf.resources.cpu is not None else None
          v_nf_mem = str(
             nf.resources.mem) if nf.resources.mem is not None else None
          v_nf_storage = str(
             nf.resources.storage) if nf.resources.storage is not None else \
            None
          # Create Node object for NF
          v_nf = virt3.Node(id=str(nf.id), name=str(nf.name),
                            type=str(nf.functional_type),
                            resources=virt3.Software_resource(cpu=v_nf_cpu,
                                                              mem=v_nf_mem,
                                                              storage=v_nf_storage))
          # Add NF to Infra object
          virtualizer.nodes[str(u)].NF_instances.add(v_nf)
          # Cache discovered NF
          discovered_nfs.append(nf.id)
          self.log.debug(
             "Add NF: %s to Infra node(id=%s, name=%s, type=%s)" % (
               nf, virtualizer.nodes[str(u)].id.get_as_text(),
               virtualizer.nodes[str(u)].name.get_as_text(),
               virtualizer.nodes[str(u)].type.get_as_text()))
          # Add NF ports
          for port in nffg[v].ports:
            self.log.debug(
               "Add Port: %s to NF node: %s" % (port, v_nf.id.get_as_text()))
            nf_port = virt3.Port(id=str(port.id), port_type="port-abstract")
            virtualizer.nodes[str(u)].NF_instances[str(v)].ports.add(nf_port)
        else:
          self.log.debug("%s is already exist in the Virtualizer(id=%s, "
                         "name=%s)" % (nf, virtualizer.id.get_as_text(),
                                       virtualizer.name.get_as_text()))
      # Add flowrules to Virtualizer
      fe_cntr = 0
      # traverse every port in the Infra node
      for port in infra.ports:
        # Check every flowrule
        for flowrule in port.flowrules:
          self.log.debug("Convert flowrule: %s" % flowrule)

          # Define metadata
          fe_id = "ESCAPE-flowentry" + str(fe_cntr)
          fe_cntr += 1
          fe_pri = str(100)

          # Check if match starts with in_port
          fe = flowrule.match.split(';')
          if fe[0].split('=')[0] != "in_port":
            self.log.warning(
               "Missing 'in_port' from match in %s. Skip flowrule "
               "conversion..." % flowrule)
            continue

          # Check if the src port is a physical or virtual port
          in_port = fe[0].split('=')[1]
          if str(port.id) in virtualizer.nodes[
            str(infra.id)].ports.port.keys():
            # Flowrule in_port is a phy port in Infra Node
            in_port = virtualizer.nodes[str(infra.id)].ports[str(port.id)]
            self.log.debug(
               "Identify in_port: %s in match as a physical port in the "
               "Virtualizer" % in_port.id.get_as_text())
          else:
            self.log.debug(
               "Identify in_port: %s in match as a dynamic port. Tracking "
               "associated NF port in the Virtualizer..." % in_port)
            # in_port is a dynamic port --> search for connected NF's port
            nf_port = [l.dst for u, v, l in
                       nffg.network.out_edges_iter([infra.id], data=True) if
                       l.type == NFFG.TYPE_LINK_DYNAMIC and str(
                          l.src.id) == in_port]
            # There should be only one link between infra and NF
            if len(nf_port) < 1:
              self.log.warning(
                 "NF port is not found for dynamic Infra port: %s defined in "
                 "match field! Skip flowrule conversion..." % in_port)
              continue
            nf_port = nf_port[0]
            in_port = virtualizer.nodes[str(infra.id)].NF_instances[
              str(nf_port.node.id)].ports[str(nf_port.id)]
            self.log.debug("Found associated NF port: node=%s, port=%s" % (
              in_port.get_parent().get_parent().id.get_as_text(),
              in_port.id.get_as_text()))

          # Process match field
          match = self.__convert_flowrule_match(domain=self.domain,
                                                match=flowrule.match)

          # Check if action starts with outport
          fe = flowrule.action.split(';')
          if fe[0].split('=')[0] != "output":
            self.log.warning(
               "Missing 'output' from action in %s. Skip flowrule "
               "conversion..." % flowrule)
            continue

          # Check if the dst port is a physical or virtual port
          out_port = fe[0].split('=')[1]
          if str(out_port) in virtualizer.nodes[
            str(infra.id)].ports.port.keys():
            # Flowrule output is a phy port in Infra Node
            out_port = virtualizer.nodes[str(infra.id)].ports[str(out_port)]
            self.log.debug(
               "Identify outport: %s in action as a physical port in the "
               "Virtualizer" % out_port.id.get_as_text())
          else:
            self.log.debug(
               "Identify outport: %s in action as a dynamic port. Track "
               "associated NF port in the Virtualizer..." % out_port)
            # out_port is a dynamic port --> search for connected NF's port
            nf_port = [l.dst for u, v, l in
                       nffg.network.out_edges_iter([infra.id], data=True) if
                       l.type == NFFG.TYPE_LINK_DYNAMIC and str(
                          l.src.id) == out_port]
            if len(nf_port) < 1:
              self.log.warning(
                 "NF port is not found for dynamic Infra port: %s defined in "
                 "action field! Skip flowrule conversion..." % out_port)
              continue
            nf_port = nf_port[0]
            out_port = virtualizer.nodes[str(infra.id)].NF_instances[
              str(nf_port.node.id)].ports[str(nf_port.id)]
            self.log.debug("Found associated NF port: node=%s, port=%s" % (
              # out_port.parent.parent.parent.id.get_as_text(),
              out_port.get_parent().get_parent().id.get_as_text(),
              out_port.id.get_as_text()))

          # Process action field
          action = self.__convert_flowrule_action(domain=self.domain,
                                                  action=flowrule.action)

          # Add Flowentry with converted params
          virt_fe = Flowentry(id=fe_id, priority=fe_pri, port=in_port,
                              match=match,
                              action=action, out=out_port)
          # virt_fe.bind(relative=True)
          self.log.debug("Generated Flowentry:\n%s" % virtualizer.nodes[
            infra.id].flowtable.add(virt_fe))

    self.log.debug("NFFG adaptation is finished.")
    virtualizer.bind(relative=True)
    # Return with modified Virtualizer
    return virtualizer

  def __convert_flowrule_match (self, domain, match):
    """
    Convert Flowrule match field from NFFG format to Virtualizer according to
    domain.

    :param domain: domain name
    :param match: flowrule match field
    :return: converted data
    """
    # E.g.:  "match": "in_port=1;TAG=sap1-comp-55"
    if len(match.split(';')) < 2:
      return

    op = match.split(';')[1].split('=')
    if op[0] not in ('TAG',):
      self.log.warning("Unsupported match operand: %s" % op[0])
      return

    if domain == NFFG.DOMAIN_OS:
      if op[0] == "TAG":
        # E.g.: <match>dl_vlan=0x0037</match>
        try:
          vlan = int(op[1].split('|')[-1])
          return r"dl_vlan=%s" % format(vlan, '#06x')
        except ValueError:
          self.log.warning(
             "Wrong VLAN format: %s! Skip flowrule conversion..." % op[1])
          return

    elif domain == NFFG.DOMAIN_UN:
      if op[0] == "TAG":
        # E.g.: <match><vlan_id>55</vlan_id></match>
        try:
          vlan = int(op[1].split('|')[-1])
        except ValueError:
          self.log.warning(
             "Wrong VLAN format: %s! Skip flowrule conversion..." % op[1])
          return
        xml = ET.Element('match')
        vlan_id = ET.SubElement(xml, 'vlan_id')
        vlan_id.text = str(vlan)
        return xml

  def __convert_flowrule_action (self, domain, action):
    """
    Convert Flowrule action field from NFFG format to Virtualizer according
    to domain.

    :param domain: domain name
    :param action: flowrule action field
    :return: converted data
    """
    # E.g.:  "action": "output=2;UNTAG"
    if len(action.split(';')) < 2:
      return

    op = action.split(';')[1].split('=')
    if op[0] not in ('TAG', 'UNTAG'):
      self.log.warning("Unsupported action operand: %s" % op[0])
      return

    if domain == "OPENSTACK":
      if op[0] == "TAG":
        # E.g.: <action>push_vlan:0x8100,set_field:0x0037</action>
        try:
          vlan = int(op[1].split('|')[-1])
          # return r"push_vlan:0x8100,set_field:%s" % format(vlan, '#06x')
          return r"mod_vlan_vid:%s" % format(vlan, '#06x')
        except ValueError:
          self.log.warning(
             "Wrong VLAN format: %s! Skip flowrule conversion..." % op[1])
          return

      elif op[0] == "UNTAG":
        # E.g.: <action>strip_vlan</action>
        return r"strip_vlan"

    elif domain == "UN":
      if op[0] == "TAG":
        # E.g.: <action><vlan><push>55<push/></vlan></action>
        try:
          vlan = int(op[1].split('|')[-1])
        except ValueError:
          self.log.warning(
             "Wrong VLAN format: %s! Skip flowrule conversion..." % op[1])
          return
        xml = ET.Element('action')
        push = ET.SubElement(ET.SubElement(xml, 'vlan'), "push")
        push.text = str(vlan)
        return xml

      elif op[0] == "UNTAG":
        # E.g.: <action><vlan><pop/></vlan></action>
        xml = ET.Element('action')
        ET.SubElement(ET.SubElement(xml, 'vlan'), "pop")
        return xml


def test_xml_based_builder ():
  # builder = NFFGtoXMLBuilder()
  # infra = builder.add_infra()
  # port = builder.add_node_port(infra, NFFGtoXMLBuilder.PORT_ABSTRACT)
  # res = builder.add_node_resource(infra, "10 VCPU", "32 GB", "5 TB")
  # link = builder.add_inter_infra_link(port, port, delay="5ms",
  #                                     bandwidth="10Gbps")
  # nf_inst = builder.add_nf_instance(infra)
  # nf_port = builder.add_node_port(nf_inst,
  # NFFGtoXMLBuilder.PORT_ABSTRACT)
  # sup_nf = builder.add_supported_nf(infra)
  # res_sup = builder.add_node_resource(sup_nf, 10, 10, 10)
  # builder.add_node_port(sup_nf, NFFGtoXMLBuilder.PORT_ABSTRACT)
  # builder.add_flow_entry(infra, port, nf_port,
  #                        action="mod_dl_src=12:34:56:78:90:12", delay="5ms",
  #                        bandwidth="10Gbps")

  # Generate same output as Agent_http.py
  # builder = XMLBasedNFFGBuilder()
  # builder.id = "UUID-ETH-001"
  # builder.name = "ETH OpenStack-OpenDaylight domain"
  # infra = builder.add_infra(
  #   name="single Bis-Bis node representing the whole domain")
  # infra_port0 = builder.add_node_port(infra, name="OVS-north external port")
  # infra_port1 = builder.add_node_port(infra, name="OVS-south external port")
  # builder.add_node_resource(infra, cpu="10 VCPU", mem="32 GB", storage="5 TB")
  # nf1 = builder.add_nf_instance(infra, id="NF1", name="example NF")
  # nf1port0 = builder.add_node_port(nf1, name="Example NF input port")
  # nf1port1 = builder.add_node_port(nf1, name="Example NF output port")
  # sup_nf = builder.add_supported_nf(infra, id="nf_a",
  #                                   name="tcp header compressor")
  # builder.add_node_port(sup_nf, name="in", param="...")
  # builder.add_node_port(sup_nf, name="out", param="...")
  # builder.add_flow_entry(infra, in_port=infra_port0, out_port=nf1port0)
  # builder.add_flow_entry(infra, in_port=nf1port1, out_port=infra_port1,
  #                        action="mod_dl_src=12:34:56:78:90:12")
  # print builder
  pass


def test_topo_un ():
  topo = """
<virtualizer>
    <name>Single node</name>
    <nodes>
        <node>
            <NF_instances>
                <node>
                    <name>DPI NF</name>
                    <ports>
                        <port>
                            <name>NF input port</name>
                            <port_type>port-abstract</port_type>
                            <id>1</id>
                        </port>
                        <port>
                            <name>NF output port</name>
                            <port_type>port-abstract</port_type>
                            <id>2</id>
                        </port>
                    </ports>
                    <type>dpi</type>
                    <id>NF1</id>
                </node>
            </NF_instances>
            <flowtable>
                <flowentry>
                    <port>../../../ports/port[id=1]</port>
                    <priority>100</priority>
                    <action>
                        <vlan>
                            <pop/>
                        </vlan>
                    </action>
                    <id>1</id>
                    <match>
                        <vlan_id>2</vlan_id>
                    </match>
                    <out>../../../NF_instances/node[id=NF1]/ports/port[id=1]
                    </out>
                </flowentry>
                <flowentry>
                    <port>../../../NF_instances/node[id=NF1]/ports/port[id=2]
                    </port>
                    <action>
                        <vlan>
                            <push>3</push>
                        </vlan>
                    </action>
                    <id>2</id>
                    <out>../../../ports/port[id=1]</out>
                </flowentry>
            </flowtable>
            <capabilities>
                <supported_NFs>
                    <node>
                        <name>DPI based on libpcre</name>
                        <ports>
                            <port>
                                <name>VNF port 1</name>
                                <port_type>port-abstract</port_type>
                                <id>1</id>
                            </port>
                            <port>
                                <name>VNF port 2</name>
                                <port_type>port-abstract</port_type>
                                <id>2</id>
                            </port>
                        </ports>
                        <type>dpi</type>
                        <id>NF1</id>
                    </node>
                    <node>
                        <name>iptables based firewall</name>
                        <ports>
                            <port>
                                <name>VNF port 1</name>
                                <port_type>port-abstract</port_type>
                                <id>1</id>
                            </port>
                            <port>
                                <name>VNF port 2</name>
                                <port_type>port-abstract</port_type>
                                <id>2</id>
                            </port>
                        </ports>
                        <type>firewall</type>
                        <id>NF2</id>
                    </node>
                    <node>
                        <name>NAT based on iptables</name>
                        <ports>
                            <port>
                                <name>VNF port 1</name>
                                <port_type>port-abstract</port_type>
                                <id>1</id>
                            </port>
                            <port>
                                <name>VNF port 2</name>
                                <port_type>port-abstract</port_type>
                                <id>2</id>
                            </port>
                        </ports>
                        <type>nat</type>
                        <id>NF3</id>
                    </node>
                    <node>
                        <name>ntop monitor</name>
                        <ports>
                            <port>
                                <name>VNF port 1</name>
                                <port_type>port-abstract</port_type>
                                <id>1</id>
                            </port>
                            <port>
                                <name>VNF port 2</name>
                                <port_type>port-abstract</port_type>
                                <id>2</id>
                            </port>
                        </ports>
                        <type>monitor</type>
                        <id>NF4</id>
                    </node>
                    <node>
                        <name>example VNF with several implementations</name>
                        <ports>
                            <port>
                                <name>VNF port 1</name>
                                <port_type>port-abstract</port_type>
                                <id>1</id>
                            </port>
                            <port>
                                <name>VNF port 2</name>
                                <port_type>port-abstract</port_type>
                                <id>2</id>
                            </port>
                        </ports>
                        <type>example</type>
                        <id>NF5</id>
                    </node>
                </supported_NFs>
            </capabilities>
            <ports>
                <port>
                    <name>OVS-north external port</name>
                    <port_type>port-sap</port_type>
                    <id>1</id>
                    <sap>SAP34</sap>
                </port>
            </ports>
            <type>BisBis</type>
            <id>UUID11</id>
            <resources>
                <mem>32 GB</mem>
                <storage>5 TB</storage>
                <cpu>10 VCPU</cpu>
            </resources>
            <name>Universal Node</name>
        </node>
    </nodes>
    <id>UUID001</id>
</virtualizer>
  """
  return topo


def test_topo_os ():
  topo = """
<virtualizer>
    <name>ETH OpenStack-OpenDaylight domain with request</name>
    <nodes>
        <node>
            <NF_instances>
                <node>
                    <name>Parental control B.4</name>
                    <ports>
                        <port>
                            <name>in</name>
                            <capability>...</capability>
                            <port_type>port-abstract</port_type>
                            <id>NF1_in</id>
                        </port>
                    </ports>
                    <type>1</type>
                    <id>NF1</id>
                    <resources>
                        <mem>1024</mem>
                    </resources>
                </node>
            </NF_instances>
            <flowtable>
                <flowentry>
                    <port>../../../ports/port[id=0]</port>
                    <action>strip_vlan</action>
                    <id>f1</id>
                    <match>dl_vlan=1</match>
                    <out>
                        ../../../NF_instances/node[id=NF1]/ports/port[id=NF1_in]
                    </out>
                </flowentry>
                <flowentry>
                    <port>
                        ../../../NF_instances/node[id=NF1]/ports/port[id=NF1_in]
                    </port>
                    <action>mod_vlan_vid:2</action>
                    <id>f2</id>
                    <out>../../../ports/port[id=0]</out>
                </flowentry>
            </flowtable>
            <capabilities>
                <supported_NFs>
                    <node>
                        <name>image0</name>
                        <ports>
                            <port>
                                <name>input port</name>
                                <port_type>port-abstract</port_type>
                                <id>0</id>
                            </port>
                        </ports>
                        <type>0</type>
                        <id>NF0</id>
                    </node>
                    <node>
                        <name>image1</name>
                        <ports>
                            <port>
                                <name>input port</name>
                                <port_type>port-abstract</port_type>
                                <id>0</id>
                            </port>
                        </ports>
                        <type>1</type>
                        <id>NF1</id>
                        <resources>
                            <mem>1024</mem>
                        </resources>
                    </node>
                </supported_NFs>
            </capabilities>
            <ports>
                <port>
                    <name>OVS-north external port</name>
                    <port_type>port-sap</port_type>
                    <id>0</id>
                    <sap>SAP24</sap>
                </port>
            </ports>
            <type>BisBis</type>
            <id>UUID-01</id>
            <resources>
                <mem>32 GB</mem>
                <storage>5 TB</storage>
                <cpu>10 VCPU</cpu>
            </resources>
            <name>single Bis-Bis node representing the whole domain</name>
        </node>
    </nodes>
    <id>UUID-ETH-001-req1</id>
</virtualizer>
"""
  return topo


if __name__ == "__main__":
  # test_xml_based_builder()
  # txt = test_virtualizer3_based_builder()
  # txt = test_topo_un()
  # txt = test_topo_os()
  # print txt
  # print Virtualizer3BasedNFFGBuilder.parse(txt)
  c = NFFGConverter(domain="OPENSTACK")
  # nffg, vv = c.parse_from_Virtualizer3(xml_data=txt)
  # # UN
  # nffg.network.node['UUID11'].ports[1].add_flowrule(
  #   match="in_port=1;TAG=sap1-comp-42", action="output=2;UNTAG")
  # OS
  # nffg.network.node['UUID-01'].ports[1].add_flowrule(
  #   match="in_port=1;TAG=sap1-comp-42", action="output=0;UNTAG")
  # nffg.network.node['UUID-01'].ports[1].add_flowrule(
  #   match="in_port=1;TAG=sap1-comp-42", action="output=0;UNTAG")
  # from pprint import pprint
  #
  # pprint(nffg.network.__dict__)
  # print nffg.dump()

  # from nffg import gen
  #
  # nffg = gen()
  # print nffg.dump()
  # v = c.dump_to_Virtualizer3(nffg, virtualizer=vv)
  # v, nffg = c.dump_to_Virtualizer3(nffg)
  # out = str(v)
  # out = out.replace("&lt;", "<").replace("&gt;", ">")
  # print out

  # with open(
  #    "../../../../examples/escape-mn-topo.nffg") as f:
  #   nffg = NFFG.parse(raw_data=f.read())
  #   nffg.duplicate_static_links()
  # print "Parsed NFFG: %s" % nffg
  # virt = c.dump_to_Virtualizer3(nffg=nffg)
  # print "Converted:"
  # print virt.xml()
  # print "Reconvert to NFFG:"
  # nffg, v = c.parse_from_Virtualizer3(xml_data=virt.xml())
  # print nffg.dump()

  with open(
     "../../../../examples/escape-mn-dov.xml") as f:
    tree = tree = ET.ElementTree(ET.fromstring(f.read()))
    dov = virt3.Virtualizer().parse(root=tree.getroot())
  nffg, v = c.parse_from_Virtualizer3(xml_data=dov.xml())
  print nffg.dump()
