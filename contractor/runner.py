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
import json
import sdag2
from stevedore import extension

LOG = logging.getLogger(__name__)


class Runner(object):
    environment = None
    config = None
    tasks = None
    dag = None

    def __init__(self, config, environment):
        self.environment = environment
        self._load_config(config)
        self._load_tasks()
        self._build_dag()

    def _load_config(self, config):
        fh = open(config)
        self.config = json.load(fh)

    def _load_tasks(self):
        self.tasks = {}

        def _load_task(ext):
            LOG.debug('Loading task: %s (Provides: %s, Depends: %r)', ext.name,
                      ext.plugin.provides, ext.plugin.depends)
            task = ext.plugin(self, self.environment)
            self.tasks[ext.plugin.provides] = task

        mgr = extension.ExtensionManager(
            namespace='contractor.tasks',
            propagate_map_exceptions=True,
        )

        mgr.map(_load_task)

    def _build_dag(self):
        # Build the empty DAG, and add the vertices
        self.dag = sdag2.DAG()
        vertices = {}

        for name in self.tasks.keys():
            vertices[name] = self.dag.add(name)

        # Iterate the tasks, adding edges where necessary
        for name, task in self.tasks.items():
            for depend in task.depends:
                self.dag.add_edge(depend, name)

    def execute(self):
        store = {}

        topo = self.dag.topologicaly()

        self._execute_introspect(topo, store)
        self._execute_build(topo, store)
        self._execute_comission(topo, store)

        topo.reverse()

        self._execute_decomission(topo, store)
        self._execute_destroy(topo, store)

    def _execute_introspect(self, topo, store):
        LOG.info('Executing introspect phase')

        for name in topo:
            task = self.tasks[name]
            LOG.info('Running introspect for task: %s', name)
            task.introspect(store)

    def _execute_build(self, topo, store):
        LOG.info('Executing build phase')

        for name in topo:
            task = self.tasks[name]
            LOG.info('Running build for task: %s', name)
            task.build(store)

    def _execute_comission(self, topo, store):
        LOG.info('Executing comission phase')

        for name in topo:
            task = self.tasks[name]
            LOG.info('Running comission for task: %s', name)
            task.comission(store)

    def _execute_decomission(self, topo, store):
        LOG.info('Executing decomission phase')

        for name in topo:
            task = self.tasks[name]
            LOG.info('Running decomission for task: %s', name)
            task.decomission(store)

    def _execute_destroy(self, topo, store):
        LOG.info('Executing destroy phase')

        for name in topo:
            task = self.tasks[name]
            LOG.info('Running destroy for task: %s', name)
            task.destroy(store)
