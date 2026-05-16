# FreeTSA test fixtures

PEM-encoded copies of FreeTSA's published certificates, fetched on 2026-05-16
for use in test_crypto_tsa.py PKIX verification tests.

Source URLs (public, no auth, served over HTTPS):

  tsa.crt      https://freetsa.org/files/tsa.crt
  cacert.pem   https://freetsa.org/files/cacert.pem

Subjects:

  tsa.crt    O=Free TSA, OU=TSA, CN=www.freetsa.org
  cacert.pem O=Free TSA, OU=Root CA, CN=www.freetsa.org (self-signed)

These are NOT secrets. FreeTSA publishes them so anyone receiving a TSR
from https://freetsa.org/tsr can verify it. They're shipped in the repo
so the PKIX integration test
(test_verify_rfc3161_against_live_freetsa_pkix_chain) can run without
needing extra network calls beyond the live TSR fetch itself.

If FreeTSA rotates its cert chain, the live test will start failing and
these files should be re-fetched.
