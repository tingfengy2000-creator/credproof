abi <abi/4.0>,
#include <tunables/global>
profile credproof-ci-container /opt/credproof-runtime/isolation/tools/usr/bin/bwrap flags=(unconfined) { userns, }
