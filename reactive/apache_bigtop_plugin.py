from charms.reactive import is_state, remove_state, set_state, when, when_any, when_none, when_not
from charmhelpers.core import hookenv
from charms.layer.apache_bigtop_base import get_bigtop_base, get_hadoop_version


@when('hadoop-plugin.joined')
@when_not('namenode.joined')
def blocked(principal):
    hookenv.status_set('blocked', 'missing required namenode relation')


@when('puppet.available', 'hadoop-plugin.joined', 'namenode.joined')
@when_not('apache-bigtop-plugin.hdfs.installed')
def install_hadoop_client_hdfs(principal, namenode):
    """Install if the namenode has sent its FQDN.

    We only need the namenode FQDN to perform the plugin install, so poll for
    namenodes() data whenever we have a namenode relation. This allows us to
    install asap, even if 'namenode.ready' is not set yet.
    """
    if namenode.namenodes():
        hookenv.status_set('maintenance', 'installing plugin (hdfs)')
        nn_host = namenode.namenodes()[0]
        bigtop = get_bigtop_base()
        hosts = {'namenode': nn_host}
        bigtop.install(hosts=hosts, roles='hadoop-client')
        set_state('apache-bigtop-plugin.hdfs.installed')
        hookenv.status_set('maintenance', 'plugin (hdfs) installed')
    else:
        hookenv.status_set('waiting', 'waiting for namenode fqdn')


@when('apache-bigtop-plugin.hdfs.installed')
@when('hadoop-plugin.joined', 'namenode.joined')
@when_not('namenode.ready')
def send_nn_spec(principal, namenode):
    """Send our plugin spec so the namenode can become ready."""
    bigtop = get_bigtop_base()
    # Send plugin spec (must match NN spec for 'namenode.ready' to be set)
    namenode.set_local_spec(bigtop.spec())


@when('apache-bigtop-plugin.hdfs.installed')
@when('hadoop-plugin.joined', 'namenode.ready')
@when_not('apache-bigtop-plugin.hdfs.ready')
def send_principal_hdfs_info(principal, namenode):
    """Send HDFS data when the namenode becomes ready."""
    principal.set_installed(get_hadoop_version())
    principal.set_hdfs_ready(namenode.namenodes(), namenode.port())
    set_state('apache-bigtop-plugin.hdfs.ready')


@when('apache-bigtop-plugin.hdfs.ready')
@when('hadoop-plugin.joined')
@when_not('namenode.ready')
def clear_hdfs_ready(principal):
    principal.clear_hdfs_ready()
    remove_state('apache-bigtop-plugin.hdfs.ready')
    remove_state('apache-bigtop-plugin.hdfs.installed')


@when('puppet.available', 'hadoop-plugin.joined', 'resourcemanager.joined')
@when_not('apache-bigtop-plugin.yarn.installed')
def install_hadoop_client_yarn(principal, resourcemanager):
    if resourcemanager.resourcemanagers():
        hookenv.status_set('maintenance', 'installing plugin (yarn)')
        # RM will send both NN and RM, no need to get data from the NN here
        nn_host = resourcemanager.resourcemanagers()[0]
        rm_host = resourcemanager.resourcemanagers()[1]
        bigtop = get_bigtop_base()
        hosts = {'namenode': nn_host, 'resourcemanager': rm_host}
        bigtop.install(hosts=hosts, roles='hadoop-client')
        set_state('apache-bigtop-plugin.yarn.installed')
        hookenv.status_set('active', 'ready (HDFS & YARN)')
    else:
        hookenv.status_set('waiting', 'waiting for resourcemanager fqdn')


@when('apache-bigtop-plugin.yarn.installed')
@when('hadoop-plugin.joined', 'resourcemanager.joined')
@when_not('resourcemanager.ready')
def send_rm_spec(principal, resourcemanager):
    """Send our plugin spec so the resourcemanager can become ready."""
    bigtop = get_bigtop_base()
    # Send plugin spec (must match RM spec for 'resourcemanager.ready' to be set)
    resourcemanager.set_local_spec(bigtop.spec())


@when('apache-bigtop-plugin.yarn.installed')
@when('hadoop-plugin.joined', 'resourcemanager.ready')
@when_not('apache-bigtop-plugin.yarn.ready')
def send_principal_yarn_info(principal, resourcemanager):
    """Send YARN data when the resourcemanager becomes ready."""
    version = get_hadoop_version()
    principal.set_installed(version)
    principal.set_yarn_ready(
        resourcemanager.resourcemanagers(), resourcemanager.port(),
        resourcemanager.hs_http(), resourcemanager.hs_ipc())
    set_state('apache-bigtop-plugin.yarn.ready')


@when('apache-bigtop-plugin.yarn.ready')
@when('hadoop-plugin.joined')
@when_not('resourcemanager.ready')
def clear_yarn_ready(principal):
    principal.clear_yarn_ready()
    remove_state('apache-bigtop-plugin.yarn.ready')
    remove_state('apache-bigtop-plugin.yarn.installed')


@when_any('apache-bigtop-plugin.hdfs.installed', 'apache-bigtop-plugin.yarn.installed')
@when('hadoop-plugin.joined')
@when_none('namenode.spec.mismatch', 'resourcemanager.spec.mismatch')
def update_status(principal):
    hdfs_rel = is_state('namenode.joined')
    yarn_rel = is_state('resourcemanager.joined')
    hdfs_ready = is_state('namenode.ready')
    yarn_ready = is_state('resourcemanager.ready')

    if not (hdfs_rel or yarn_rel):
        hookenv.status_set('blocked',
                           'missing namenode and/or resourcemanager relation')
    elif hdfs_rel and not hdfs_ready:
        hookenv.status_set('waiting', 'waiting for hdfs')
    elif yarn_rel and not yarn_ready:
        hookenv.status_set('waiting', 'waiting for yarn')
    else:
        ready = []
        if hdfs_ready:
            ready.append('hdfs')
        if yarn_ready:
            ready.append('yarn')
        hookenv.status_set('active', 'ready ({})'.format(' & '.join(ready)))
