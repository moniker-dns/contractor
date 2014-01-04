from contractor.ssh import SSHConnection

KEY = """
-----BEGIN RSA PRIVATE KEY-----
MIIEpQIBAAKCAQEA2m8caICx3mPDP39UdP8y3ELhjeIzIEGe2JUfDYQIxKPl/Y/q
MqQroHlEe2abxSejv7BQhpCw6QCzpU4k/vYVs2RHpUkCHwGGIubYtzbV4CW4icpQ
UBFdXJ/R/t+GMAQfat2gjLxjrHqiMRAWo+/5pDfYWhMTmbRLTuWZ/kSK0o8EvRni
uWRr0d7qGuyUZ+lfW4hmFhaXnJP6e6c1RuAi9QTzh95yVgnFgIEgme7piv7v9rlH
/6S72yIw36d7Sqw5d3WxyukHRYor+gQCBZYOlwVgV/7nrHw3FdtpvK0skSmP02V0
+vWo4xaUkHB4FfIkTOPkV4QbWByUh0UwxwsykwIDAQABAoIBAFlH3wGr0IfImQ6E
Gd40TPKQd6bJlQITMDzwPqAEnpzZLPFF+IC4b4iI6H/TwcmE2T5Jb7CAxX6HJeZk
GWUI6nfHfi1FuRM5ST1Mw7mnNSYH5PSU99yyLEnmnSui6zMHDFxet/euLMNb4J1T
KR3awVvo44p1j6ZcdgeKezXdiCxlPNNtPYneRPGXOQTS2p8Kjxc55ofDb67dAMRr
YU7SNvtpdMeNRPH2ljHav/UW4zakRTtSiMQTM8qWHSo6GHHC6f08D3WlI6EtSA2r
6SzIijedjqqQS/jNg3pHNfE2ENSWeyq7R0xrz+XAsBPP4c+C5KQ1VAEoSLv2Fli0
JMNds2ECgYEA/UnQN8zL2YV3AurA3t6yeD8SX/P07x1XWOMSqCAVXG6nu3pgnAa+
icIZlwJEQOzo1Jne4a8ixdnLqGCP9APEDEsx+iy3ISFWuUVUm6OXPNYLxP6QI1wf
H/Puw0M+CqserX4x8B7nxr6BH9TOpCpij4IwV3Cg5HPlJ2YKx4wa05ECgYEA3MXF
w5bmvSwEGrfogq9TV8AkRtsOrIlmF609pz/a0sfEZxdwlilqNxq+VbWvrsRgSd7P
SzIgbL3qSOu91Kt/ygJlN48DTAsYjYXY5bi1J6srG9cidatg8Gj5I5bDmvCSOx04
7Yn1qcfWm1j1Mi93HTmK05bnP5rg9llyUuj5ieMCgYEA26oZV1tYa0SRi0kWjfLr
KtfgUrEbegijSSZddsukWu5or3IZuRcsRgK8+LbxhLEx17e+kVG3QYl6U4OzNLfT
XaoVJNeE1sm4EaOsFfLRZeRofqcbUF9Daw29w0Bc3Rm82E/6dToIXte22mlP8RYF
Nlp9HEhEcPyF/x5DOP4sAdECgYEA0+A6W+uGpiaICdxWGJWKtryAFEBHZO64PCDW
+pwdtgxiQU4Njw9QEHJqGHe1k1SD1GExMEl7NOFO54zXMjMlAQoreZaW43QCrE+4
ST9rHBb52E4vlB5VemRENhOKxjf7HyB8cfvk+HwBSjWlm/RRrIp84XQBmtlY7RQK
0+cjFWECgYEAi9VUjEmuiCzoCW2oQL0zVf4lmr753DfJasd2d9yKO+TdOavcsm2w
liewgMPeju8Dm3N90I6CzXmc4mvsxIbL93GG5OG3gOBsuTWGOy1s2TDUMatVik0L
bCh2ocA4pNYYfnqo+jhmHaXF0XxtsMeXllbHRz1SM/cReDAH0mtG4Oc=
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
    conn2 = SSHConnection('127.0.0.1', 'ubuntu2', KEY, port=lport)

    (stdout, stderr, ) = conn2.execute('/usr/bin/whoami')

    print "Who am I? %s" % stdout.read(100)
except:
    pass
finally:
    conn2.disconnect()
    conn.disconnect()

