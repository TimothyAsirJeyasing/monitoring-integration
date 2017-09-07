import __builtin__
import traceback
import json


import signal
import maps
import gevent
import os


from tendrl.monitoring_integration.grafana import utils
from tendrl.monitoring_integration.grafana import exceptions
from tendrl.monitoring_integration.grafana import dashboard
from tendrl.monitoring_integration.grafana import datasource
from tendrl.monitoring_integration.grafana import webhook_receiver 
from tendrl.commons import manager as common_manager
from tendrl import monitoring_integration
from tendrl.monitoring_integration import sync
from tendrl.commons import TendrlNS
from tendrl.commons.utils import log_utils as logger


class MonitoringIntegrationManager(common_manager.Manager):

    def __init__(self):

        self._complete = gevent.event.Event()
        super(
            MonitoringIntegrationManager,
            self
        ).__init__(
            NS.sync_thread
        )
        self.webhook_receiver = webhook_receiver.WebhookReceiver()

    def start(self):

        super(MonitoringIntegrationManager, self).start()
        # Creating Default Dashboards
        _upload_default_dashboards()
        self.webhook_receiver.start()



def _upload_default_dashboards():

        monitoring_integration_manager = MonitoringIntegrationManager()

        dashboards = []
        utils.get_conf()
        dashboards = dashboard.get_all_dashboards()

        title = []

        for dashboard_json in dashboards:
            title.append(dashboard_json["uri"].split('/')[1])

        for dashboard_json in NS.config.data["dashboards"]:
            if dashboard_json in title:
                msg = '\n' + "Dashboard " + str(dashboard_json) + \
                      " already exists" + '\n'
                logger.log("info", NS.get("publisher_id", None),
                           {'message': msg})
                continue
            response = dashboard.create_dashboard(dashboard_json)

            if response.status_code == 200:
                msg = '\n' + "Dashboard " + str(dashboard_json)+ \
                      " uploaded successfully" + '\n'
                logger.log("info", NS.get("publisher_id", None),
                           {'message': msg})
            else:
                msg = "Dashboard {0} upload failed. Error code: {1} ," + \
                      "Error message: " + \
                      "{2} ".format(str(dashboard_json),
                                    str(response.status_code),
                                    str(get_message_from_response(response)))
                logger.log("info", NS.get("publisher_id", None),
                           {'message': msg})
        try:
            dashboard_json = dashboard.get_dashboard(NS.config.data["home_dashboard"])

            if 'dashboard' in dashboard_json:
                dashboard_id = dashboard_json.get('dashboard').get('id')
                response = dashboard.set_home_dashboard(dashboard_id)

                response = dashboard.set_home_dashboard(dashboard_id)
                if response.status_code == 200:
                    msg = '\n' + "Dashboard " + \
                          str(NS.config.data["home_dashboard"]) + \
                          " is set as home dashboard" + '\n'
                    logger.log("info", NS.get("publisher_id", None),
                           {'message': msg})
            else:
                msg = '\n' + str(dashboard_json.get('message')) + '\n'
                logger.log("info", NS.get("publisher_id", None),
                           {'message': msg})
        except exceptions.ConnectionFailedException as ex:
            traceback.print_exc()
            logger.log("error", NS.get("publisher_id", None),
                       {'message': str(ex)})
            raise exceptions.ConnectionFailedException

        # Creating datasource
        response = datasource.create_datasource()
        if response.status_code == 200:
            msg = '\n' + "Datasource " + \
                  " uploaded successfully" + '\n'
            logger.log("info", NS.get("publisher_id", None),
                       {'message': msg})

        else:
            msg = "Datasource upload failed. Error code: {0} ," + \
                  "Error message: " + \
                  "{1} ".format(response.status_code,
                                str(get_message_from_response(response)))
            logger.log("info", NS.get("publisher_id", None),
                       {'message': msg})

def get_message_from_response(response_data):

    message = ""
    try :
        if isinstance(json.loads(response_data._content), list):
            message = str(json.loads(response._content)[0]["message"])
        else:
            message = str(json.loads(response_data._content)["message"])
    except (AttributeError, KeyError):
        pass

    return message

def main():

    monitoring_integration.MonitoringIntegrationNS()

    TendrlNS()
    NS.type = "monitoring"
    NS.publisher_id = "monitoring_integration"
    if NS.config.data.get("with_internal_profiling", False):
        from tendrl.commons import profiler
        profiler.start()
    NS.monitoring.config.save()
    NS.monitoring.definitions.save()
    NS.sync_thread = sync.MonitoringIntegrationSdsSyncThread()

    monitoring_integration_manager = MonitoringIntegrationManager()
    monitoring_integration_manager.start()
    complete = gevent.event.Event()
    NS.node_context = NS.node_context.load()
    current_tags = list(NS.node_context.tags)
    current_tags += ["tendrl/integration/monitoring"]
    NS.node_context.tags = list(set(current_tags))
    NS.node_context.save()

    def shutdown():
        complete.set()
        NS.sync_thread.stop()

    gevent.signal(signal.SIGTERM, shutdown)
    gevent.signal(signal.SIGINT, shutdown)

    while not complete.is_set():
        complete.wait(timeout=1)


if __name__ == '__main__':
    main()
