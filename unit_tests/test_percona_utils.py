import os
import unittest
import sys
import tempfile

import mock

sys.modules['MySQLdb'] = mock.Mock()
import percona_utils

from test_utils import CharmTestCase


class UtilsTests(unittest.TestCase):
    def setUp(self):
        super(UtilsTests, self).setUp()

    @mock.patch("percona_utils.log")
    def test_update_empty_hosts_file(self, mock_log):
        map = {'1.2.3.4': 'my-host'}
        with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
            percona_utils.HOSTS_FILE = tmpfile.name
            percona_utils.HOSTS_FILE = tmpfile.name
            percona_utils.update_hosts_file(map)

        with open(tmpfile.name, 'r') as fd:
            lines = fd.readlines()

        os.remove(tmpfile.name)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "%s %s\n" % (map.items()[0]))

    @mock.patch("percona_utils.log")
    def test_update_hosts_file_w_dup(self, mock_log):
        map = {'1.2.3.4': 'my-host'}
        with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
            percona_utils.HOSTS_FILE = tmpfile.name

            with open(tmpfile.name, 'w') as fd:
                fd.write("%s %s\n" % (map.items()[0]))

            percona_utils.update_hosts_file(map)

        with open(tmpfile.name, 'r') as fd:
            lines = fd.readlines()

        os.remove(tmpfile.name)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "%s %s\n" % (map.items()[0]))

    @mock.patch("percona_utils.log")
    def test_update_hosts_file_entry(self, mock_log):
        altmap = {'1.1.1.1': 'alt-host'}
        map = {'1.1.1.1': 'hostA',
               '2.2.2.2': 'hostB',
               '3.3.3.3': 'hostC',
               '4.4.4.4': 'hostD'}
        with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
            percona_utils.HOSTS_FILE = tmpfile.name

            with open(tmpfile.name, 'w') as fd:
                fd.write("#somedata\n")
                fd.write("%s %s\n" % (altmap.items()[0]))

            percona_utils.update_hosts_file(map)

        with open(percona_utils.HOSTS_FILE, 'r') as fd:
            lines = fd.readlines()

        os.remove(tmpfile.name)
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[0], "#somedata\n")
        self.assertEqual(lines[1], "%s %s\n" % (map.items()[0]))
        self.assertEqual(lines[4], "%s %s\n" % (map.items()[3]))

    @mock.patch("percona_utils.log")
    @mock.patch("percona_utils.config")
    @mock.patch("percona_utils.update_hosts_file")
    @mock.patch("percona_utils.get_host_ip")
    @mock.patch("percona_utils.relation_get")
    @mock.patch("percona_utils.related_units")
    @mock.patch("percona_utils.relation_ids")
    def test_get_cluster_hosts(self, mock_rel_ids, mock_rel_units,
                               mock_rel_get, mock_get_host_ip,
                               mock_update_hosts_file, mock_config,
                               mock_log):
        mock_rel_ids.return_value = [1]
        mock_rel_units.return_value = [2]
        mock_get_host_ip.return_value = 'hostA'

        def _mock_rel_get(*args, **kwargs):
            return {'private-address': '0.0.0.0'}

        mock_rel_get.side_effect = _mock_rel_get
        mock_config.side_effect = lambda k: False

        hosts = percona_utils.get_cluster_hosts()

        self.assertFalse(mock_update_hosts_file.called)
        mock_rel_get.assert_called_with(rid=1, unit=2)
        self.assertEqual(hosts, ['hostA', 'hostA'])

    @mock.patch.object(percona_utils, 'get_ipv6_addr')
    @mock.patch.object(percona_utils, 'log')
    @mock.patch.object(percona_utils, 'config')
    @mock.patch.object(percona_utils, 'update_hosts_file')
    @mock.patch.object(percona_utils, 'get_host_ip')
    @mock.patch.object(percona_utils, 'relation_get')
    @mock.patch.object(percona_utils, 'related_units')
    @mock.patch.object(percona_utils, 'relation_ids')
    def test_get_cluster_hosts_ipv6(self, mock_rel_ids, mock_rel_units,
                                    mock_rel_get, mock_get_host_ip,
                                    mock_update_hosts_file, mock_config,
                                    mock_log, mock_get_ipv6_addr):
        ipv6addr = '2001:db8:1:0:f816:3eff:fe79:cd'
        mock_get_ipv6_addr.return_value = [ipv6addr]
        mock_rel_ids.return_value = [88]
        mock_rel_units.return_value = [1, 2]
        mock_get_host_ip.return_value = 'hostA'

        def _mock_rel_get(*args, **kwargs):
            host_suffix = 'BC'
            id = kwargs.get('unit')
            hostname = "host{}".format(host_suffix[id - 1])
            return {'private-address': '10.0.0.{}'.format(id + 1),
                    'hostname': hostname}

        config = {'prefer-ipv6': True}
        mock_rel_get.side_effect = _mock_rel_get
        mock_config.side_effect = lambda k: config.get(k)

        hosts = percona_utils.get_cluster_hosts()

        mock_update_hosts_file.assert_called_with({ipv6addr: 'hostA',
                                                   '10.0.0.2': 'hostB',
                                                   '10.0.0.3': 'hostC'})
        mock_rel_get.assert_has_calls([mock.call(rid=88, unit=1),
                                       mock.call(rid=88, unit=2)])
        self.assertEqual(hosts, ['hostA', 'hostB', 'hostC'])

    @mock.patch.object(percona_utils, 'get_address_in_network')
    @mock.patch.object(percona_utils, 'log')
    @mock.patch.object(percona_utils, 'config')
    @mock.patch.object(percona_utils, 'relation_get')
    @mock.patch.object(percona_utils, 'related_units')
    @mock.patch.object(percona_utils, 'relation_ids')
    def test_get_cluster_hosts_w_cluster_network(self, mock_rel_ids,
                                                 mock_rel_units,
                                                 mock_rel_get,
                                                 mock_config,
                                                 mock_log,
                                                 mock_get_address_in_network):
        mock_rel_ids.return_value = [88]
        mock_rel_units.return_value = [1, 2]
        mock_get_address_in_network.return_value = '10.100.0.1'

        def _mock_rel_get(*args, **kwargs):
            host_suffix = 'BC'
            unit = kwargs.get('unit')
            hostname = "host{}".format(host_suffix[unit - 1])
            return {'private-address': '10.0.0.{}'.format(unit + 1),
                    'cluster-address': '10.100.0.{}'.format(unit + 1),
                    'hostname': hostname}

        config = {'cluster-network': '10.100.0.0/24'}
        mock_rel_get.side_effect = _mock_rel_get
        mock_config.side_effect = lambda k: config.get(k)

        hosts = percona_utils.get_cluster_hosts()
        mock_rel_get.assert_has_calls([mock.call(rid=88, unit=1),
                                       mock.call(rid=88, unit=2)])
        self.assertEqual(hosts, ['10.100.0.1', '10.100.0.2', '10.100.0.3'])

    @mock.patch.object(percona_utils, 'log', lambda *args, **kwargs: None)
    @mock.patch.object(percona_utils, 'related_units')
    @mock.patch.object(percona_utils, 'relation_ids')
    @mock.patch.object(percona_utils, 'config')
    def test_is_sufficient_peers(self, mock_config, mock_relation_ids,
                                 mock_related_units):
        _config = {'min-cluster-size': None}
        mock_config.side_effect = lambda key: _config.get(key)
        self.assertTrue(percona_utils.is_sufficient_peers())

        mock_relation_ids.return_value = ['cluster:0']
        mock_related_units.return_value = ['test/0']
        _config = {'min-cluster-size': 3}
        self.assertFalse(percona_utils.is_sufficient_peers())

        mock_related_units.return_value = ['test/0', 'test/1']
        self.assertTrue(percona_utils.is_sufficient_peers())

    @mock.patch.object(percona_utils, 'lsb_release')
    def test_packages_eq_wily(self, mock_lsb_release):
        mock_lsb_release.return_value = {'DISTRIB_CODENAME': 'wily'}
        self.assertEqual(percona_utils.determine_packages(),
                         ['percona-xtradb-cluster-server-5.6'])

    @mock.patch.object(percona_utils, 'lsb_release')
    def test_packages_gt_wily(self, mock_lsb_release):
        mock_lsb_release.return_value = {'DISTRIB_CODENAME': 'xenial'}
        self.assertEqual(percona_utils.determine_packages(),
                         ['percona-xtradb-cluster-server-5.6'])

    @mock.patch.object(percona_utils, 'lsb_release')
    def test_packages_lt_wily(self, mock_lsb_release):
        mock_lsb_release.return_value = {'DISTRIB_CODENAME': 'trusty'}
        self.assertEqual(percona_utils.determine_packages(),
                         ['percona-xtradb-cluster-server-5.5',
                          'percona-xtradb-cluster-client-5.5'])

    @mock.patch.object(percona_utils, 'get_wsrep_value')
    def test_cluster_in_sync_not_ready(self, _wsrep_value):
        _wsrep_value.side_effect = [None, None]
        self.assertFalse(percona_utils.cluster_in_sync())

    @mock.patch.object(percona_utils, 'get_wsrep_value')
    def test_cluster_in_sync_ready_syncing(self, _wsrep_value):
        _wsrep_value.side_effect = [True, None]
        self.assertFalse(percona_utils.cluster_in_sync())

    @mock.patch.object(percona_utils, 'get_wsrep_value')
    def test_cluster_in_sync_ready_sync(self, _wsrep_value):
        _wsrep_value.side_effect = [True, 4]
        self.assertTrue(percona_utils.cluster_in_sync())

    @mock.patch.object(percona_utils, 'get_wsrep_value')
    def test_cluster_in_sync_ready_sync_donor(self, _wsrep_value):
        _wsrep_value.side_effect = [True, 2]
        self.assertTrue(percona_utils.cluster_in_sync())


TO_PATCH = [
    # 'status_set',
    'is_sufficient_peers',
    'is_bootstrapped',
    'config',
    'cluster_in_sync',
]


class TestAssessStatus(CharmTestCase):
    def setUp(self):
        CharmTestCase.setUp(self, percona_utils, TO_PATCH)

    def test_single_unit(self):
        self.config.return_value = None
        self.is_sufficient_peers.return_value = True
        stat, _ = percona_utils.charm_check_func()
        assert stat == 'active'

    def test_insufficient_peers(self):
        self.config.return_value = 3
        self.is_sufficient_peers.return_value = False
        stat, _ = percona_utils.charm_check_func()
        assert stat == 'blocked'

    def test_not_bootstrapped(self):
        self.config.return_value = 3
        self.is_sufficient_peers.return_value = True
        self.is_bootstrapped.return_value = False
        stat, _ = percona_utils.charm_check_func()
        assert stat == 'waiting'

    def test_bootstrapped_in_sync(self):
        self.config.return_value = 3
        self.is_sufficient_peers.return_value = True
        self.is_bootstrapped.return_value = True
        self.cluster_in_sync.return_value = True
        stat, _ = percona_utils.charm_check_func()
        assert stat == 'active'

    def test_bootstrapped_not_in_sync(self):
        self.config.return_value = 3
        self.is_sufficient_peers.return_value = True
        self.is_bootstrapped.return_value = True
        self.cluster_in_sync.return_value = False
        stat, _ = percona_utils.charm_check_func()
        assert stat == 'blocked'

    def test_assess_status(self):
        with mock.patch.object(percona_utils, 'assess_status_func') as asf:
            callee = mock.MagicMock()
            asf.return_value = callee
            percona_utils.assess_status('test-config')
            asf.assert_called_once_with('test-config')
            callee.assert_called_once_with()

    @mock.patch.object(percona_utils, 'REQUIRED_INTERFACES')
    @mock.patch.object(percona_utils, 'services')
    @mock.patch.object(percona_utils, 'make_assess_status_func')
    def test_assess_status_func(self,
                                make_assess_status_func,
                                services,
                                REQUIRED_INTERFACES):
        services.return_value = 's1'
        percona_utils.assess_status_func('test-config')
        # ports=None whilst port checks are disabled.
        make_assess_status_func.assert_called_once_with(
            'test-config', REQUIRED_INTERFACES, charm_func=mock.ANY,
            services='s1', ports=None)

    def test_pause_unit_helper(self):
        with mock.patch.object(percona_utils, '_pause_resume_helper') as prh:
            percona_utils.pause_unit_helper('random-config')
            prh.assert_called_once_with(percona_utils.pause_unit,
                                        'random-config')
        with mock.patch.object(percona_utils, '_pause_resume_helper') as prh:
            percona_utils.resume_unit_helper('random-config')
            prh.assert_called_once_with(percona_utils.resume_unit,
                                        'random-config')

    @mock.patch.object(percona_utils, 'services')
    def test_pause_resume_helper(self, services):
        f = mock.MagicMock()
        services.return_value = 's1'
        with mock.patch.object(percona_utils, 'assess_status_func') as asf:
            asf.return_value = 'assessor'
            percona_utils._pause_resume_helper(f, 'some-config')
            asf.assert_called_once_with('some-config')
            # ports=None whilst port checks are disabled.
            f.assert_called_once_with('assessor', services='s1', ports=None)
