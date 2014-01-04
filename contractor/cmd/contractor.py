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
from __future__ import absolute_import
from contractor.openstack.common import log as logging
from contractor import runner
from oslo.config import cfg


CONF = cfg.CONF
CONF.set_default('debug', True)
CONF.set_default('verbose', True)


def main(*args):
    logging.setup('contractor')
    r = runner.Runner(config='config-staging.json', environment='ae1-2')
    r.execute()
