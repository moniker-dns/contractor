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
from contractor.openstack.common import timeutils
from contractor import ssh
from contractor.task import base
import logging
from novaclient.v1_1 import client as nv_client
#from neutronclient.common import exceptions as ne_exceptions
import time


LOG = logging.getLogger(__name__)


class NovaTask(base.Task):
    def __init__(self, runner, environment):
        super(NovaTask, self).__init__(runner, environment)

        env_config = self._get_environment_config()

        self.nv_client = nv_client.Client(
            auth_url=env_config['credentials']['auth_url'],
            username=env_config['credentials'].get('username', None),
            api_key=env_config['credentials']['password'],
            project_id=env_config['credentials'].get('project_id', None),
            tenant_id=env_config['credentials'].get('project_id', None),
            region_name=env_config['credentials'].get('region_name', None),
            http_log_debug=True,
        )

    def _get_network_id_from_name(self, store, name):
        for network in store['_os-neutron_networks']:
            if network['name'] == name:
                return network['id']

        raise Exception('BOOOO')


class BeachheadTask(NovaTask):
    provides = 'beachhead'
    depends = ['router_interface', 'network', 'subnet', 'security_group']

    def __init__(self, runner, environment):
        super(BeachheadTask, self).__init__(runner, environment)

        self.beachhead_config = self._get_environment_config()['beachhead']
        self.networks_config = self._get_environment_config()['networks']

    def build(self, store):
        beachhead_name = 'beachhead-%s' % timeutils.utcnow_ts()

        # Create the SSH Keypair
        LOG.info('Creating keypair with name %s', beachhead_name)

        keypair = self.nv_client.keypairs.create(beachhead_name)

        # TODO(kiall): Remove me!!
        LOG.info('Private Key: %s', keypair.private_key)

        # Create the beachhead instance
        nics = []
        for network in self.networks_config.keys():
            nics.append({
                'net-id': self._get_network_id_from_name(store, network),
            })

        LOG.info('Creating beachhead instance with name %s', beachhead_name)

        instance = self.nv_client.servers.create(
            name=beachhead_name,
            image=self.beachhead_config['image'],
            flavor=self.beachhead_config['flavor'],
            nics=nics,
            security_groups=['default', 'beachhead'],
            key_name=beachhead_name
        )

        # Allocate a Floating IP
        LOG.info('Allocating floating IP for beachhead instance')
        floating_ip = self.nv_client.floating_ips.create(
            self.beachhead_config.get('floating_ip_pool', None),
        )

        LOG.info('Floating IP %s Allocated', floating_ip.ip)

        # Block for the Beachhead instance to become active
        while True:
            instance = self.nv_client.servers.get(instance.id)
            if instance.status == 'ACTIVE':
                break

        # Add the floating IP
        instance.add_floating_ip(floating_ip.ip)

        # Give the Floating IP some time to become active
        time.sleep(2)

        LOG.info('Connecting to the beachhead instance')

        connection = ssh.SSHConnection(floating_ip.ip,
                                       'ubuntu',
                                       keypair.private_key)

        store['_os-nova_beachhead-keypair'] = keypair
        store['_os-nova_beachhead-instance'] = instance
        store['_os-nova_beachhead-floating_ip'] = floating_ip
        store['_os-nova_beachhead-connection'] = connection

    def destroy(self, store):
        LOG.info('Disconnecting from beachhead instance')

        connection = store['_os-nova_beachhead-connection']
        connection.disconnect()

        LOG.info('Desytoying beachhead instance. key and floating ip')

        # Delete the beachhead Instance
        instance = store['_os-nova_beachhead-instance']
        instance.delete()

        # Delete the Floating IP
        floating_ip = store['_os-nova_beachhead-floating_ip']
        floating_ip.delete()

        # Delete the SSH KeyPair
        keypair = store['_os-nova_beachhead-keypair']
        keypair.delete()


class InstanceTask(NovaTask):
    provides = 'instance'
    depends = ['router_interface', 'network', 'subnet', 'security_group',
               'beachhead']

    def __init__(self, runner, environment):
        super(InstanceTask, self).__init__(runner, environment)

        self.instances = {}

        roles_config = self.runner.config['roles']

        for role_name, role in roles_config.items():
            image = role.get('image', None)
            flavor = role.get('flavor', None)

            if image is None or flavor is None:
                LOG.warning('Skipping role %s, as there is no image and/or '
                            'flavor', role_name)

            instances = role.get('instances', {}).get(environment, [])

            for instance in instances:
                az = instance.get('az', 'az1')
                number = instance['number']

                name = 'dns-%s%s-%s%04d' % (environment, az, role_name, number)

                nics = []

                for nic in instance.get('nics', []):
                    nics.append({
                        'network': nic['network'],
                        'fixed_ip': nic.get('fixed_ip', None),
                        'floating_ip': nic.get('floating_ip', None),
                    })

                self.instances[name] = {
                    'environment': environment,
                    'role': role_name,
                    'image': image,
                    'flavor': flavor,
                    'az': az,
                    'nics': nics,
                }

    def introspect(self, store):
        instances = self.nv_client.servers.list()
        store['_os-nova_instances'] = {i.name: i for i in instances}

        existing = set([i.name for i in instances])
        expected = set(self.instances.keys())

        self.to_create = expected.difference(existing)
        self.to_update = expected.intersection(existing)
        self.to_destroy = existing.difference(expected)

        LOG.info('Instance TODO - C(%d) U(%d) D(%d)',
                 len(self.to_create),
                 len(self.to_update),
                 len(self.to_destroy))

    def build(self, store):
        LOG.info('Building %s instances', len(self.to_create))

        created_instances = []

        for name in self.to_create:
            LOG.info('Building instance with name %s', name)

            nics = []
            for nic in self.instances[name]['nics']:
                net_id = self._get_network_id_from_name(store, nic['network'])
                nics.append({
                    'net-id': net_id,
                    'v4-fixed-ip': nic['fixed_ip'],
                })

            instance = self.nv_client.servers.create(
                name=name,
                image=self.instances[name]['image'],
                flavor=self.instances[name]['flavor'],
                availability_zone=self.instances[name]['az'],
                nics=nics,
                security_groups=['default', self.instances[name]['role']],
                key_name=store['_os-nova_beachhead-keypair'].name,
                meta={
                    'environment': self.instances[name]['environment'],
                    'role': self.instances[name]['role'],
                },
            )

            created_instances.append(instance)

        # Block for instances to become "active"
        LOG.info('Blocking for %d instances to become ACTIVE',
                 len(created_instances))

        i = 0

        while i < len(created_instances):
            for instance in created_instances:
                instance = self.nv_client.servers.get(instance.id)

                LOG.info('Instance with name %s is %s', instance.name,
                         instance.status)

                if instance.status == 'ACTIVE':
                    # Add any floating IPs
                    for nic in self.instances[instance.name]['nics']:
                        if nic['floating_ip'] is not None:
                            LOG.info('Attaching floating ip %s to instance '
                                     'with name %s', nic['floating_ip'],
                                     instance.name)

                            instance.add_floating_ip(nic['floating_ip'],
                                                     nic['fixed_ip'])

                    i += 1

            time.sleep(10)

        LOG.info('All newly created instances ACTIVE')

        store['_os-nova_created-instances'] = {i.name: i for i in created_instances}
        store['_os-nova_instances'].update(store['_os-nova_created-instances'])

    def destroy(self, store):
        LOG.info('Destroying %s instances', len(self.to_destroy))

        for name in self.to_destroy:
            LOG.info('Destroying instance with name %s', name)

            server = store['_os-nova_instances'].get(name)
            server.delete()
