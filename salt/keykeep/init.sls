# keykeep — generate + deploy keykeep_encryption_key to odoo.conf
# Deploy: /srv/salt/keykeep/init.sls on the Salt master.
# Trigger from Odoo: salt.minion → "Deploy keykeep key" (saltstack_keykeep).

{% set conf = pillar.get('keykeep:odoo_conf', '/etc/odoo/odoo.conf') %}

keykeep-encryption-key:
  cmd.run:
    - name: |
        python3 - <<'PYEOF'
        conf = '{{ conf }}'
        with open(conf) as f:
            content = f.read()
        if 'keykeep_encryption_key' not in content:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            with open(conf, 'a') as f:
                f.write('\nkeykeep_encryption_key = %s\n' % key)
            print('generated')
        else:
            print('exists')
        PYEOF
    - unless: grep -q '^keykeep_encryption_key' {{ conf }}
    - runas: root

odoo-restart:
  service.running:
    - name: odoo
    - watch:
        - cmd: keykeep-encryption-key
