from contractor.ssh import SSHConnection

KEY = """
-----BEGIN RSA PRIVATE KEY-----
Key Here
-----END RSA PRIVATE KEY-----
"""

conn = SSHConnection('15.126.206.237', 'ubuntu', KEY)

print "Is Connected? %r"  % conn.connected

(stdout, stderr, ) = conn.execute('/usr/bin/whoami')

print "Is Connected? %r"  % conn.connected

print "Who am I? %s" % stdout.read(100)

print "Trying to tunnel :D"

lport = conn.tunnel('172.17.4.3')

try:
	# Use the ubuntu2 user, in order to fallback to HPCS_SSO_USERNAME when connecting as ubuntu2 fails
    conn2 = SSHConnection('127.0.0.1', 'ubuntu2', KEY, port=lport)

    (stdout, stderr, ) = conn2.execute('/usr/bin/whoami')

    print "Who am I? %s" % stdout.read(100)
except:
    pass
finally:
    conn2.disconnect()
    conn.disconnect()

