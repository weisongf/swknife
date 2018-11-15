#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import math
import re
import os
import logging
from neutronclient.v2_0 import client
from keystoneauth1 import session, loading
from xlrd import open_workbook

DEFAULT_SPEC = "general"
LOGGER = None
COLUME_NAME = ["service", "network_name", "subnet_name", "cidr", "disable_dhcp", "ip_pool", "vlanid", 'disable_gw',
               'gw', 'dns']
MAX_COLUMNS = len(COLUME_NAME)


def get_logger():
    global LOGGER
    if not LOGGER:
        LOGGER = logging.getLogger(__name__)
    return LOGGER


def setup_logging(debug=False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level)


class Network(object):
    """
    network object
    """

    def __init__(self, service, network_name, subnet_name, cidr, ip_pool, vlanid, disable_dhcp=False, disable_gw=False,
                 gw=None, dns=None):
        """

        :param service:
        :param network_name:
        :param subnet_name:
        :param cidr:
        :param disable_dhcp:
        :param ip_pool:
        :param vlanid:
        :param disable_gw:
        :param gw:
        :param dns:
        """

        self.service = service
        self.network_name = network_name
        self.subnet_name = subnet_name
        self.cidr = cidr
        self.disable_dhcp = disable_dhcp
        self.ip_pool = ip_pool
        self.vlanid = vlanid
        self.disable_gw = disable_gw
        self.disable_dhcp = disable_dhcp
        self.gw = gw
        self.dns = dns

    def create_network(self, neutron_client):

        if not neutron_client:
            raise Exception("Please initialize neutron client before continuing")

        logger = get_logger()

        networks = neutron_client.list_networks(name=self.network_name).get('networks')

        # create network if not existing
        if len(networks) == 0:
            # create this network
            network = networks[0]
        elif len(networks) == 1:
            # already exist
            network = neutron_client.create_network(self.network)
        else:
            raise Exception("There are multiple networks with same name, please check config")

        # create subnet if not existings
        subnets = neutron_client.list_subnets({
            "network_id": network.get('id'),
            "name": self.subnet_name
        })

        if len(subnets) == 0:
            neutron_client.create_subnet(self.get_subnet(network.get('id')))
        else:
            logger.warning("subnet: %s is duplicate", self.subnet_name)

    @property
    def network(self):
        network = {"network": {
            "name": self.network_name,

            # fixme configurable or not?
            "provider:network_type": "vlan",

            # fixme configrable or not?
            "provider:physical_network": "physnet1",
            "provider:segmentation_id": self.vlanid,
            "shared": True
        }}

        return network

    def get_subnet(self, network_id):
        subnet = {
            "subnet": {
                "network_id": network_id,
                "name": self.subnet_name,
                "ip_version": 4,
                "cidr": self.cidr
            }
        }

        if self.dns and len(self.dns) > 0:
            subnet.update({"dns_nameservers": self.dns})

        if not self.disable_gw and self.gw:
            subnet.update({"gateway_ip": self.gw})

        return subnet


def read_template_from_excel(config_path):
    """
    read flavor configurations from excel
    :param config_path: path to excel configuration file
    :return: a list of flavors
    """

    if not os.path.exists(config_path):
        raise Exception("path: %s does not exist!", config_path)

    logger = get_logger()
    flavors = []

    logger.info("read configuration from %s", config_path)
    wb = open_workbook(config_path)

    # by default, there is only a single sheet
    sheet = wb.sheets()[0]

    # ignore the first row
    for row in range(1, sheet.nrows):
        args = {}
        for col in range(sheet.ncols):

            # there should not be more than defined
            # number of columns
            if col > MAX_COLUMNS:
                break

            # fixme value might have letter like 'G'
            val = sheet.cell(row, col).value
            args[COLUME_NAME[col]] = val

        logger.info("args: %s", str(args))
        flavors.append(Network(**args))

    logger.info("retrieve %s records from %s", str(flavors), config_path)
    # return a list of Flavors
    return flavors


def create_networks(neutron_client, networks):
    """
    create all required flavors
    :param neutron_client
    :param networks
    :return:
    """

    if not neutron_client:
        raise Exception("neutron client has not been properly setup!")

    logger = get_logger()

    for network in networks:
        logger.info("create network %s", str(network))
        network.create_network(neutron_client)


def init_neutron_client(credentials):
    # get logger
    logger = get_logger()

    # relation between variable name & corresponding environment variable
    required_fields = {'auth_url': 'OS_AUTH_URL',
                       'username': "OS_USERNAME",
                       'password': 'OS_PASSWORD',
                       'user_domain_name': "OS_USER_DOMAIN_NAME",
                       'project_name': "OS_PROJECT_NAME",
                       'project_domain_name': "OS_PROJECT_DOMAIN_NAME"
                       }

    # check & pop values from environment variable
    options = {}
    for key in required_fields.keys():
        if not credentials.get(key):
            value = os.environ[required_fields[key]]
            if not value:
                raise Exception("%s(%s) is missing" % (key, required_fields[key]))
            options.update({key: value})
        else:
            options.update({key: credentials.get(key)})

    logger.info("begin initializing nova client")
    loader = loading.get_plugin_loader('v3password')
    auth = loader.load_from_options(**options)
    sess = session.Session(auth=auth, verify=False)

    # fixme fix this ugle code!!
    endpoint_type = credentials.get('endpoint_type', os.environ['OS_ENDPOINT_TYPE'])
    endpoint_type = endpoint_type if endpoint_type else "public"
    region_name = credentials.get('region_name', os.environ['OS_REGION_NAME'])
    region_name = region_name if region_name else "RegionOne"

    nova_client = client.Client(session=sess, endpoint_type=endpoint_type, region_name=region_name)
    logger.info("initialzing neutron client completed successfully")

    # return a glance client
    return nova_client


def get_parser():
    import argparse

    parser = argparse.ArgumentParser(description='generate required flavors')
    parser.add_argument('-f', '--config', dest='config_path', required=True,
                        help='path to the configuration file')
    parser.add_argument('-d', '--debug', dest='debug', action='store_const', const=True,
                        default=False, help='enable debugging')

    return parser.parse_args()


def main():
    """
    program entrance
    :return:
    """

    parser = get_parser()

    # setup loggings
    setup_logging(debug=parser.debug)

    # assemble flavor objects
    logger = get_logger()
    logger.info('configuration found at %s', parser.config_path)
    networks = read_template_from_excel(parser.config_path)

    # init nova client
    # fixme read credentials from command line & config files?
    neutron_client = init_neutron_client({})

    # create requested flavors
    create_networks(neutron_client, networks)

    return 0


if __name__ == "__main__":
    exit(main())
