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
import paramiko
import logging
import cStringIO
import socket
import os
import select
import SocketServer
import threading

LOG = logging.getLogger(__name__)


class SSHConnection(object):
    def __init__(self, hostname, username, private_key, port=22):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        self.hostname = hostname
        self.port = port
        self.username = username

        pk_fk = cStringIO.StringIO(private_key)
        self.private_key = paramiko.RSAKey.from_private_key(pk_fk)

        self._connected = False
        self._tunnels = []

    def connect(self):
        try:
            try:
                username = os.environ.get('HPCS_SSO_USERNAME', 'ubuntu')
                LOG.debug("Trying to connect with user %s", username)
                self._connect(username)
            except paramiko.AuthenticationException:
                LOG.debug("Trying to connect with user %s", self.username)
                self._connect(self.username, self.private_key)
        except paramiko.BadHostKeyException:
            raise Exception('This should never happen')
        except paramiko.AuthenticationException:
            raise Exception('Authentication Failed')
        except paramiko.SSHException:
            raise Exception('Unknown SSH Exception')
        except socket.error, e:
            raise Exception('Unknown Socket Error')
        else:
            self._connected = True

    def _connect(self, username, private_key=None):
        self.client.connect(
            hostname=self.hostname,
            port=self.port,
            username=username,
            pkey=private_key,
            allow_agent=True,
            look_for_keys=True,
        )

    def disconnect(self):
        for thread in self._tunnels:
            thread.stop()

        self.client.close()

    @property
    def connected(self):
        if self._connected:
            try:
                self.client.exec_command('/bin/pwd')
            except paramiko.SSHException:
                self._connected = False

        return self._connected

    def execute(self, command):
        if not self.connected:
            self.connect()

        try:
            (_, stdout, stderr, ) = self.client.exec_command(command)
        except paramiko.SSHException:
            raise Exception('Failed to execute command :(')

        LOG.debug('Command StdOut: %s', stdout)
        LOG.debug('Command StdErr: %s', stderr)

        return (stdout, stderr, )

    def tunnel(self, hostname, port=22):
        if not self.connected:
            self.connect()

        class _ForwardHandler(_ForwardHandlerBase):
            chain_host = hostname
            chain_port = port
            ssh_transport = self.client.get_transport()

        local_port = 9002
        server = _ForwardServer(('', local_port), _ForwardHandler)

        thread = _ForwardThread(server)
        thread.start()

        self._tunnels.append(thread)

        return local_port


class _ForwardThread(threading.Thread):
    def __init__(self, server):
        super(_ForwardThread, self).__init__()
        self.server = server
        self.running = False

    def run(self):
        LOG.debug('Starting ServerThread')
        self.running = True
        self.server.serve_forever()

    def stop(self):
        LOG.debug('Stopping ServerThread')

        if self.running:
            self.running = False
            self.server.shutdown()
            self.join()


class _ForwardServer(SocketServer.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


class _ForwardHandlerBase(SocketServer.BaseRequestHandler):
     def handle(self):
        try:
            chan = self.ssh_transport.open_channel('direct-tcpip',
                                                   (self.chain_host, self.chain_port),
                                                   self.request.getpeername())
        except Exception, e:
            LOG.error('Incoming request to %s:%d failed: %s', self.chain_host,
                                                              self.chain_port,
                                                              repr(e))
            return

        if chan is None:
            LOG.error('Incoming request to %s:%d was rejected by the SSH '
                      'server.', self.chain_host, self.chain_port)
            return

        LOG.debug('Connected! Tunnel open %r -> %r -> %r',
                  self.request.getpeername(),
                  chan.getpeername(),
                  (self.chain_host, self.chain_port))

        while True:
            r, w, x = select.select([self.request, chan], [], [])

            if self.request in r:
                data = self.request.recv(1024)

                if len(data) == 0:
                    break

                chan.send(data)

            if chan in r:
                data = chan.recv(1024)

                if len(data) == 0:
                    break

                self.request.send(data)

        peername = self.request.getpeername()

        chan.close()
        self.request.close()

        LOG.debug('Disconnected! Tunnel closed from %r', peername)