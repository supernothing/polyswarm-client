# Downstream

Note that CI variables:

* CI_POLYSWARM_CLIENT_DOWNSTREAM
* CI_PROP_ENGINES

are a space separated list of projects that depend on `polyswarm-client`

This build chain currently:

1. Directly kicks linux engines (e.g. Ikarus)
1. Indirectly kicks Windows engines (e.g. K7) by kicking off the packer build in `polyswarm-client-windows`