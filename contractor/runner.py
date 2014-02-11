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
import json
import logging
import sdag2
from stevedore import extension

LOG = logging.getLogger(__name__)


class Runner(object):
    def __init__(self, config, environment):
        self.store = {}

        self.environment = environment

        self._load_config(config)
        self._load_tasks()
        self._build_dag()

    def _load_config(self, config):
        fh = open(config)
        self.config = json.load(fh)

    def _load_tasks(self):
        self.task_classes = {}

        def _load_task(ext):
            LOG.debug('Loading task: %s (Provides: %s, Depends: %r)', ext.name,
                      ext.plugin.provides, ext.plugin.depends)
            self.task_classes[ext.plugin.provides] = ext.plugin

        mgr = extension.ExtensionManager(
            namespace='contractor.tasks',
            propagate_map_exceptions=True,
        )

        mgr.map(_load_task)

    def _build_dag(self):
        # Build the empty DAG, and add the vertices
        self.dag = sdag2.DAG()
        vertices = {}

        for name in self.task_classes.keys():
            vertices[name] = self.dag.add(name)

        # Iterate the tasks, adding edges where necessary
        for name, task in self.task_classes.items():
            # Add ordinary depends
            for depend in task.depends:
                self.dag.add_edge(depend, name)

            # Add reverse depends
            for rdepend in task.rdepends:
                self.dag.add_edge(name, rdepend)

    def execute(self):
        self.tasks = {}

        topo = self.dag.topologicaly()

        LOG.info('Task execution order: %s', topo)

        for name in topo:
            LOG.debug('Initializing task: %s', name)
            task = self.task_classes[name](self, self.environment, self.store)
            self.tasks[name] = task

        self._execute_introspect(topo)
        self._execute_build(topo)
        self._execute_comission(topo)

        topo.reverse()

        self._execute_decomission(topo)
        self._execute_destroy(topo)

    def _execute_introspect(self, topo):
        LOG.info('Executing introspect phase')

        for name in topo:
            task = self.tasks[name]
            if task.enabled:
                LOG.info('Running introspect for task: %s', name)
                task.introspect()

    def _execute_build(self, topo):
        LOG.info('Executing build phase')

        for name in topo:
            task = self.tasks[name]
            if task.enabled:
                LOG.info('Running build for task: %s', name)
                task.build()

    def _execute_comission(self, topo):
        LOG.info('Executing comission phase')

        for name in topo:
            task = self.tasks[name]
            if task.enabled:
                LOG.info('Running comission for task: %s', name)
                task.comission()

    def _execute_decomission(self, topo):
        LOG.info('Executing decomission phase')

        for name in topo:
            task = self.tasks[name]
            if task.enabled:
                LOG.info('Running decomission for task: %s', name)
                task.decomission()

    def _execute_destroy(self, topo):
        LOG.info('Executing destroy phase')

        for name in topo:
            task = self.tasks[name]
            if task.enabled:
                LOG.info('Running destroy for task: %s', name)
                task.destroy()
