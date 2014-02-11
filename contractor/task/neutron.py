# Copyright 2013 Hewlett-Packard Development Company, L.P.
#
# Author: Kiall Mac Innes <kiall@hp.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import logging
from contractor.task import base
from neutronclient.v2_0 import client as ne_client
from neutronclient.common import exceptions as ne_exceptions


LOG = logging.getLogger(__name__)


class NeutronTask(base.Task):
    def __init__(self, runner, environment, store):
        super(NeutronTask, self).__init__(runner, environment, store)

        env_config = self._get_environment_config()

        self.ne_client = ne_client.Client(
            auth_url=env_config['credentials']['auth_url'],
            username=env_config['credentials'].get('username', None),
            user_id=env_config['credentials'].get('user_id', None),
            password=env_config['credentials']['password'],
            tenant_name=env_config['credentials'].get('project_name', None),
            tenant_id=env_config['credentials'].get('project_id', None),
            region_name=env_config['credentials'].get('region_name', None),
        )

    def _get_network_id_from_name(self, name):
        for network in self.store['_os-neutron_networks']:
            if network['name'] == name:
                return network['id']

        raise Exception('Failed to find network with name: %s', name)

    def _get_subnet_id_from_name(self, name):
        for subnet in self.store['_os-neutron_subnets']:
            if subnet['name'] == name:
                return subnet['id']

        raise Exception('Failed to find subnet with name: %s', name)

    def _get_router_id_from_name(self, name):
        for router in self.store['_os-neutron_routers']:
            if router['name'] == name:
                return router['id']

        raise Exception('Failed to find router with name: %s', name)


class RouterTask(NeutronTask):
    provides = 'router'
    depends = []

    routers_to_create = None
    routers_to_update = None
    routers_to_destroy = None

    def introspect(self):
        routers = self.ne_client.list_routers()['routers']
        self.store['_os-neutron_routers'] = routers

        existing_routers = set([r['name'] for r in routers])
        expected_routers = set(self._get_environment_config()['routers'].keys())

        self.routers_to_create = expected_routers.difference(existing_routers)
        self.routers_to_update = expected_routers.intersection(existing_routers)
        self.routers_to_destroy = existing_routers.difference(expected_routers)

        LOG.info('Router TODO - C(%d) U(%d) D(%d)',
                 len(self.routers_to_create),
                 len(self.routers_to_update),
                 len(self.routers_to_destroy))

    def build(self):
        router_config = self._get_environment_config()['routers']

        for name in self.routers_to_create:
            LOG.info('Creating router %s', name)

            c = router_config[name]

            body = {
                'router': {
                    'name': name,
                    'external_gateway_info': c.get('external_gateway_info', {})
                }
            }

            resp = self.ne_client.create_router(body=body)
            LOG.info('Router %s created with id %s', name, resp['router']['id'])
            self.store['_os-neutron_routers'].append(resp['router'])

    def destroy(self):
        for name in self.routers_to_destroy:
            LOG.info('Destroying router %s', name)

            for router in self.store['_os-neutron_routers']:
                if router['name'] == name:
                    self.ne_client.delete_router(router['id'])
                    LOG.info('Router %s with id %s destroyed', name,
                             router['id'])


class NetworkTask(NeutronTask):
    provides = 'network'
    depends = ['router']

    networks_to_create = None
    networks_to_update = None
    networks_to_destroy = None

    def introspect(self):
        networks = self.ne_client.list_networks()['networks']
        self.store['_os-neutron_networks'] = networks

        existing_networks = set([n['name'] for n in networks])
        expected_networks = set(self._get_environment_config()['networks'].keys())

        self.networks_to_create = expected_networks.difference(existing_networks)
        self.networks_to_update = expected_networks.intersection(existing_networks)
        self.networks_to_destroy = existing_networks.difference(expected_networks)

        LOG.info('Network TODO - C(%d) U(%d) D(%d)',
                 len(self.networks_to_create),
                 len(self.networks_to_update),
                 len(self.networks_to_destroy))

    def build(self):
        network_config = self._get_environment_config()['networks']

        for name in self.networks_to_create:
            LOG.info('Creating network %s', name)

            c = network_config[name]

            body = {
                'network': {
                    'name': name
                }
            }

            resp = self.ne_client.create_network(body=body)
            LOG.info('Network %s created with id %s', name, resp['network']['id'])
            self.store['_os-neutron_networks'].append(resp['network'])

    def destroy(self):
        for name in self.networks_to_destroy:
            LOG.info('Skipping destroy of network %s', name)
            if name == 'Ext-Net':
                continue

            LOG.info('Destroying network %s', name)

            for network in self.store['_os-neutron_networks']:
                if network['name'] == name:
                    self.ne_client.delete_network(network['id'])
                    LOG.info('Network %s with id %s destroyed', name,
                             network['id'])


class SubnetTask(NeutronTask):
    provides = 'subnet'
    depends = ['network']

    subnets_to_create = None
    subnets_to_update = None
    subnets_to_destroy = None

    def _get_subnets_from_config(self):
        subnets = {}
        networks = self._get_environment_config()['networks']

        for network_name, network in networks.items():
            nsubnets = network.get('subnets', {})

            for nsubnet in nsubnets.values():
                nsubnet['network'] = network_name

            subnets.update(nsubnets)

        return subnets

    def introspect(self):
        subnets = self.ne_client.list_subnets()['subnets']
        self.store['_os-neutron_subnets'] = subnets

        existing_subnets = set([s['name'] for s in subnets])
        expected_subnets = set(self._get_subnets_from_config().keys())

        self.subnets_to_create = expected_subnets.difference(existing_subnets)
        self.subnets_to_update = expected_subnets.intersection(existing_subnets)
        self.subnets_to_destroy = existing_subnets.difference(expected_subnets)

        LOG.info('Subnet TODO - C(%d) U(%d) D(%d)',
                 len(self.subnets_to_create),
                 len(self.subnets_to_update),
                 len(self.subnets_to_destroy))

    def build(self):
        subnet_config = self._get_subnets_from_config()

        for name in self.subnets_to_create:
            LOG.info('Creating subnets %s', name)

            c = subnet_config[name]

            network_id = self._get_network_id_from_name(c['network'])

            body = {
                'subnet': {
                    'name': name,
                    'network_id': network_id,
                    'ip_version': c.get('ip_version', 4),
                    'cidr': c['cidr'],
                }
            }

            resp = self.ne_client.create_subnet(body=body)
            LOG.info('Subnet %s created with id %s', name, resp['subnet']['id'])
            self.store['_os-neutron_subnets'].append(resp['subnet'])

    def destroy(self):
        for name in self.subnets_to_destroy:
            LOG.info('Destroying subnet %s', name)

            for subnet in self.store['_os-neutron_subnets']:
                if subnet['name'] == name:
                    self.ne_client.delete_subnet(subnet['id'])
                    LOG.info('Subnet %s with id %s destroyed', name,
                             subnet['id'])


class RouterInterfaceTask(NeutronTask):
    provides = 'router_interface'
    depends = ['subnet', 'router']

    def _parse_config(self):
        router_interfaces = []

        routers = self._get_environment_config()['routers']

        for router_name, router in routers.items():
            LOG.info("Found Router Name %s", router_name)
            rsubnets = router.get('subnets', [])

            for rsubnet in rsubnets:
                LOG.info("Found Router Subnet %s", rsubnet)
                router_interfaces.append((router_name, rsubnet, ))

        return router_interfaces

    def introspect(self):
        ri_config = self._parse_config()

        # TODO...
        self.ri_to_create = ri_config
        self.ri_to_update = []
        self.ri_to_destroy = []

        LOG.info('Router Interface TODO - C(%d) U(%d) D(%d)',
                 len(self.ri_to_create),
                 len(self.ri_to_update),
                 len(self.ri_to_destroy))

    def build(self):
        for ri in self.ri_to_create:
            router_id = self._get_router_id_from_name(ri[0])
            subnet_id = self._get_subnet_id_from_name(ri[1])

            body = {"subnet_id": subnet_id}

            try:
                self.ne_client.add_interface_router(router_id, body)
            except ne_exceptions.NeutronClientException as e:
                if 'Router already has a port on subnet' in str(e):
                    pass
                else:
                    raise

class SecurityGroupTask(NeutronTask):
    provides = 'security_group'
    depends = []

    def __init__(self, runner, environment, store):
        super(SecurityGroupTask, self).__init__(runner, environment, store)

        self.security_groups = {
            'default': {
                'description': 'Default Security Group'
            },
            'beachhead': {
                'description': 'Beachhead Security Group'
            }
        }

        defined_security_groups = set()

        defined_security_groups.update(self.runner.config['security_groups'].keys())
        defined_security_groups.update(self.runner.config['roles'].keys())

        for group_name in defined_security_groups:
            self.security_groups[group_name] = {
                'description': '%s instances' % group_name,
            }

    def introspect(self):
        security_groups = self.ne_client.list_security_groups()['security_groups']

        self.store['_os-neutron_security_groups'] = {s['name']: s for s in security_groups}

        existing = set([s['name'] for s in security_groups])
        expected = set(self.security_groups.keys())

        self.to_create = expected.difference(existing)
        self.to_update = expected.intersection(existing)
        self.to_destroy = existing.difference(expected)

        LOG.info('Security Group TODO - C(%d) U(%d) D(%d)',
                 len(self.to_create),
                 len(self.to_update),
                 len(self.to_destroy))

    def build(self):
        LOG.info('Building %s security groups', len(self.to_create))

        for name in self.to_create:
            LOG.info('Building security group with name %s', name)

            body = {
                "security_group": {
                    "name": name,
                    "description": self.security_groups[name]['description'],
                },
            }

            self.ne_client.create_security_group(body)

    def destroy(self):
        LOG.info('Destroying %s security groups', len(self.to_destroy))

        for name in self.to_destroy:
            LOG.info('Destroying security group with name %s', name)
            security_group_id = self.store['_os-neutron_security_groups'][name]['id']

            self.ne_client.delete_security_group(security_group_id)

class SecurityGroupRuleTask(NeutronTask):
    provides = 'security_group_rules'
    depends = ['security_groups']

    def __init__(self, runner, environment, store):
        super(SecurityGroupRoleTask, self).__init__(runner, environment, store)

    def introspect(self):
        pass

    def build(self):
        pass

    def destroy(self):
        pass
