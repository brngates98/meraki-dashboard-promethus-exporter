import http.server
import threading
import time
import configargparse
import meraki


def get_devices(devices, dashboard, organizationId):
    devices.extend(dashboard.organizations.getOrganizationDevicesStatuses(organizationId=organizationId, total_pages="all"))
    print('Got', len(devices), 'Devices')


def get_device_statuses(devicesdtatuses, dashboard, organizationId):
    devicesdtatuses.extend(dashboard.organizations.getOrganizationDevicesUplinksLossAndLatency(organizationId=organizationId, ip='8.8.8.8', timespan="120", total_pages="all"))
    print('Got ', len(devicesdtatuses), 'Device Statuses')


def get_uplink_statuses(uplinkstatuses, dashboard, organizationId):
    uplinkstatuses.extend(dashboard.appliance.getOrganizationApplianceUplinkStatuses(organizationId=organizationId, total_pages="all"))
    print('Got ', len(uplinkstatuses), 'Uplink Statuses')


def get_vpn_statuses(vpnstatuses, dashboard, organizationId):
    vpnstatuses.extend(dashboard.appliance.getOrganizationApplianceVpnStatuses(organizationId=organizationId, total_pages="all"))
    print('Got ', len(vpnstatuses), 'VPN Statuses')


def get_organization(org_data, dashboard, organizationId):
    org_data.update(dashboard.organizations.getOrganization(organizationId=organizationId))


def get_organizations(orgs_list, dashboard):
    response = dashboard.organizations.getOrganizations()
    for org in response:
        try:
            dashboard.organizations.getOrganizationApiRequestsOverview(organizationId=org['id'])
            orgs_list.append(org['id'])
        except meraki.exceptions.APIError:
            pass


def get_latest_sensor_readings(sensor_readings, dashboard, organizationId):
    response = dashboard.sensor.getOrganizationSensorReadingsLatest(organizationId=organizationId, total_pages="all")
    sensor_readings.extend(response)
    print('Got', len(sensor_readings), 'Sensor Readings')


def get_usage(dashboard, organizationId):
    devices = []
    t1 = threading.Thread(target=get_devices, args=(devices, dashboard, organizationId))
    t1.start()

    devicesdtatuses = []
    t2 = threading.Thread(target=get_device_statuses, args=(devicesdtatuses, dashboard, organizationId))
    t2.start()

    uplinkstatuses = []
    t3 = threading.Thread(target=get_uplink_statuses, args=(uplinkstatuses, dashboard, organizationId))
    t3.start()

    vpnstatuses = []
    t4 = threading.Thread(target=get_vpn_statuses, args=(vpnstatuses, dashboard, organizationId))
    t4.start()

    org_data = {}
    t5 = threading.Thread(target=get_organization, args=(org_data, dashboard, organizationId))
    t5.start()

    sensor_readings = []
    t6 = threading.Thread(target=get_latest_sensor_readings, args=(sensor_readings, dashboard, organizationId))
    t6.start()

    t1.join()
    t2.join()
    t3.join()
    t4.join()
    t5.join()
    t6.join()

    print('Combining collected data\n')

    the_list = {}
    values_list = ['name', 'model', 'mac', 'wan1Ip', 'wan2Ip', 'lanIp', 'publicIp', 'networkId', 'status', 'usingCellularFailover']
    for device in devices:
        the_list[device['serial']] = {}
        the_list[device['serial']]['orgName'] = org_data['name']
        for value in values_list:
            try:
                if device[value] is not None:
                    the_list[device['serial']][value] = device[value]
            except KeyError:
                pass

    for device in devicesdtatuses:
        try:
            the_list[device['serial']]
        except KeyError:
            the_list[device['serial']] = {"missing data": True}

        the_list[device['serial']]['latencyMs'] = device['timeSeries'][-1]['latencyMs']
        the_list[device['serial']]['lossPercent'] = device['timeSeries'][-1]['lossPercent']

    for device in uplinkstatuses:
        try:
            the_list[device['serial']]
        except KeyError:
            the_list[device['serial']] = {"missing data": True}
        the_list[device['serial']]['uplinks'] = {}
        for uplink in device['uplinks']:
            the_list[device['serial']]['uplinks'][uplink['interface']] = uplink['status']

    for vpn in vpnstatuses:
        try:
            the_list[vpn['deviceSerial']]
        except KeyError:
            the_list[vpn['deviceSerial']] = {"missing data": True}

        the_list[vpn['deviceSerial']]['vpnMode'] = vpn['vpnMode']
        the_list[vpn['deviceSerial']]['exportedSubnets'] = [subnet['subnet'] for subnet in vpn['exportedSubnets']]
        the_list[vpn['deviceSerial']]['merakiVpnPeers'] = vpn['merakiVpnPeers']
        the_list[vpn['deviceSerial']]['thirdPartyVpnPeers'] = vpn['thirdPartyVpnPeers']

    for sensor in sensor_readings:
        try:
            the_list[sensor['serial']]
        except KeyError:
            the_list[sensor['serial']] = {"missing data": True}

        for reading in sensor['readings']:
            metric = reading['metric']
            if metric == 'temperature':
                if 'temperature' not in the_list[sensor['serial']]:
                    the_list[sensor['serial']]['temperature'] = {}
                the_list[sensor['serial']]['temperature']['celsius'] = reading.get('temperature', {}).get('celsius')
                the_list[sensor['serial']]['temperature']['fahrenheit'] = reading.get('temperature', {}).get('fahrenheit')
            elif metric == 'humidity':
                the_list[sensor['serial']]['humidity'] = reading.get('humidity', {}).get('relativePercentage')
            elif metric == 'battery':
                the_list[sensor['serial']]['battery'] = reading.get('battery', {}).get('percentage')
            elif metric == 'button':
                the_list[sensor['serial']]['button'] = reading.get('button', {}).get('pressType')
            elif metric == 'co2':
                the_list[sensor['serial']]['co2'] = reading.get('co2', {}).get('concentration')
            elif metric == 'current':
                the_list[sensor['serial']]['current'] = reading.get('current', {}).get('draw')
            elif metric == 'door':
                the_list[sensor['serial']]['door'] = int(reading.get('door', {}).get('open', 0))
            elif metric == 'downstreamPower':
                the_list[sensor['serial']]['downstreamPower'] = int(reading.get('downstreamPower', {}).get('enabled', 0))
            elif metric == 'frequency':
                the_list[sensor['serial']]['frequency'] = reading.get('frequency', {}).get('level')
            elif metric == 'indoorAirQuality':
                the_list[sensor['serial']]['indoorAirQuality'] = reading.get('indoorAirQuality', {}).get('score')
            elif metric == 'noise':
                the_list[sensor['serial']]['noise'] = reading.get('noise', {}).get('ambient', {}).get('level')
            elif metric == 'pm25':
                the_list[sensor['serial']]['pm25'] = reading.get('pm25', {}).get('concentration')
            elif metric == 'powerFactor':
                the_list[sensor['serial']]['powerFactor'] = reading.get('powerFactor', {}).get('percentage')
            elif metric == 'realPower':
                the_list[sensor['serial']]['realPower'] = reading.get('realPower', {}).get('draw')
            elif metric == 'remoteLockoutSwitch':
                the_list[sensor['serial']]['remoteLockoutSwitch'] = int(reading.get('remoteLockoutSwitch', {}).get('locked', 0))
            elif metric == 'tvoc':
                the_list[sensor['serial']]['tvoc'] = reading.get('tvoc', {}).get('concentration')
            elif metric == 'voltage':
                the_list[sensor['serial']]['voltage'] = reading.get('voltage', {}).get('level')
            elif metric == 'water':
                the_list[sensor['serial']]['water'] = int(reading.get('water', {}).get('present', 0))

    print('Done')
    return the_list


class MyHandler(http.server.BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()

    def _set_headers_404(self):
        self.send_response(404)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()

    def do_GET(self):
        if "/?target=" not in self.path and "/organizations" not in self.path:
            self._set_headers_404()
            return

        self._set_headers()
        dashboard = meraki.DashboardAPI(API_KEY, output_log=False, print_console=True)

        if "/organizations" in self.path:
            org_list = list()
            get_organizations(org_list, dashboard)
            response = "- targets:\n   - " + "\n   - ".join(org_list)
            self.wfile.write(response.encode('utf-8'))
            self.wfile.write("\n".encode('utf-8'))
            return

        dest_orgId = self.path.split('=')[1]
        print('Target: ', dest_orgId)
        organizationId = str(dest_orgId)

        start_time = time.monotonic()

        host_stats = get_usage(dashboard, organizationId)
        print("Reporting on:", len(host_stats), "hosts")

        uplink_statuses = {'active': 0, 'ready': 1, 'connecting': 2, 'not connected': 3, 'failed': 4}

        response = """
# HELP meraki_device_latency The latency of the Meraki device in milliseconds
# TYPE meraki_device_latency gauge
# UNIT meraki_device_latency milliseconds
# HELP meraki_device_loss_percent The packet loss percentage of the Meraki device
# TYPE meraki_device_loss_percent gauge
# UNIT meraki_device_loss_percent percent
# HELP meraki_device_status The status of the Meraki device (1 for online, 0 for offline)
# TYPE meraki_device_status gauge
# UNIT meraki_device_status boolean
# HELP meraki_device_uplink_status The status of the uplink of the Meraki device
# TYPE meraki_device_uplink_status gauge
# UNIT meraki_device_uplink_status status_code
# HELP meraki_device_using_cellular_failover Whether the Meraki device is using cellular failover (1 for true, 0 for false)
# TYPE meraki_device_using_cellular_failover gauge
# UNIT meraki_device_using_cellular_failover boolean
# HELP meraki_vpn_mode The VPN mode of the Meraki device (1 for hub, 0 for spoke)
# TYPE meraki_vpn_mode gauge
# UNIT meraki_vpn_mode boolean
# HELP meraki_vpn_exported_subnets The exported subnets of the Meraki VPN
# TYPE meraki_vpn_exported_subnets gauge
# UNIT meraki_vpn_exported_subnets count
# HELP meraki_vpn_meraki_peers The Meraki VPN peers of the Meraki VPN
# TYPE meraki_vpn_meraki_peers gauge
# UNIT meraki_vpn_meraki_peers count
# HELP meraki_vpn_third_party_peers The third-party VPN peers of the Meraki VPN
# TYPE meraki_vpn_third_party_peers gauge
# UNIT meraki_vpn_third_party_peers count
"""

        for host in host_stats.keys():
            try:
                target = '{serial="' + host + \
                         '",name="' + (host_stats[host]['name'] if host_stats[host]['name'] != "" else host_stats[host]['mac']) + \
                         '",networkId="' + host_stats[host]['networkId'] + \
                         '",orgName="' + host_stats[host]['orgName'] + \
                         '",orgId="' + organizationId + \
                         '"'
            except KeyError:
                break
            try:
                if host_stats[host]['latencyMs'] is not None:
                    response += 'meraki_device_latency' + target + '} ' + str(host_stats[host]['latencyMs'] / 1000) + '\n'
                if host_stats[host]['lossPercent'] is not None:
                    response += 'meraki_device_loss_percent' + target + '} ' + str(host_stats[host]['lossPercent']) + '\n'
            except KeyError:
                pass
            try:
                response += 'meraki_device_status' + target + '} ' + ('1' if host_stats[host]['status'] == 'online' else '0') + '\n'
            except KeyError:
                pass
            try:
                response += 'meraki_device_using_cellular_failover' + target + '} ' + ('1' if host_stats[host]['usingCellularFailover'] else '0') + '\n'
            except KeyError:
                pass
            if 'uplinks' in host_stats[host]:
                for uplink in host_stats[host]['uplinks'].keys():
                    response += 'meraki_device_uplink_status' + target + ',uplink="' + uplink + '"} ' + str(uplink_statuses[host_stats[host]['uplinks'][uplink]]) + '\n'
            if 'vpnMode' in host_stats[host]:
                response += 'meraki_vpn_mode' + target + '} ' + ('1' if host_stats[host]['vpnMode'] == 'hub' else '0') + '\n'
            if 'exportedSubnets' in host_stats[host]:
                for subnet in host_stats[host]['exportedSubnets']:
                    response += 'meraki_vpn_exported_subnets' + target + ',subnet="' + subnet + '"} 1\n'
            if 'merakiVpnPeers' in host_stats[host]:
                for peer in host_stats[host]['merakiVpnPeers']:
                    reachability_value = '1' if peer['reachability'] == 'reachable' else '0'
                    response += 'meraki_vpn_meraki_peers' + target + ',peer_networkId="' + peer['networkId'] + '",peer_networkName="' + peer['networkName'] + '",reachability="' + peer['reachability'] + '"} ' + reachability_value + '\n'
            if 'thirdPartyVpnPeers' in host_stats[host]:
                for peer in host_stats[host]['thirdPartyVpnPeers']:
                    reachability_value = '1' if peer['reachability'] == 'reachable' else '0'
                    response += 'meraki_vpn_third_party_peers' + target + ',peer_name="' + peer['name'] + '",peer_publicIp="' + peer['publicIp'] + '",reachability="' + peer['reachability'] + '"} ' + reachability_value + '\n'

            for metric in ['apparentPower', 'battery', 'button', 'co2', 'current', 'door', 'downstreamPower', 'frequency', 'humidity', 'indoorAirQuality', 'noise', 'pm25', 'powerFactor', 'realPower', 'remoteLockoutSwitch', 'temperature', 'tvoc', 'voltage', 'water']:
                if metric in host_stats[host]:
                    if isinstance(host_stats[host][metric], dict):
                        for sub_metric, value in host_stats[host][metric].items():
                            response += f'meraki_sensor_{metric}_{sub_metric}' + target + '} ' + str(value) + '\n'
                    else:
                        response += f'meraki_sensor_{metric}' + target + '} ' + str(host_stats[host][metric]) + '\n'

        response += '# TYPE request_processing_seconds summary\n'
        response += 'request_processing_seconds ' + str(time.monotonic() - start_time) + '\n'

        self.wfile.write(response.encode('utf-8'))

    def do_HEAD(self):
        self._set_headers()

    def do_POST(self):
        self._set_headers_404()
        return
        self._set_headers()


if __name__ == '__main__':
    parser = configargparse.ArgumentParser(description='Per-User traffic stats Prometheus exporter for Meraki API.')
    parser.add_argument('-k', metavar='API_KEY', type=str, required=True,
                        env_var='MERAKI_API_KEY', help='API Key')
    parser.add_argument('-p', metavar='http_port', type=int, default=9822,
                        help='HTTP port to listen for Prometheus scraper, default 9822')
    parser.add_argument('-i', metavar='bind_to_ip', type=str, default="",
                        help='IP address where HTTP server will listen, default all interfaces')
    args = vars(parser.parse_args())
    HTTP_PORT_NUMBER = args['p']
    HTTP_BIND_IP = args['i']
    API_KEY = args['k']

    server_class = MyHandler
    httpd = http.server.ThreadingHTTPServer((HTTP_BIND_IP, HTTP_PORT_NUMBER), server_class)
    print(time.asctime(), "Server Starts - %s:%s" % ("*" if HTTP_BIND_IP == '' else HTTP_BIND_IP, HTTP_PORT_NUMBER))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print(time.asctime(), "Server Stops - %s:%s" % ("localhost", HTTP_PORT_NUMBER))
