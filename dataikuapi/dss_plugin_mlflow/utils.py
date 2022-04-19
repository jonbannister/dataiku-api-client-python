from ..utils import DataikuException
from ..dss.managedfolder import DSSManagedFolder
import logging
import os
import sys
import tempfile
import shutil
from base64 import b64encode


class MLflowHandle:
    def __init__(self, client, project, managed_folder, host=None):
        """ Add the MLflow-plugin parts of dataikuapi to MLflow local setup.

        This method deals with
        1. importing dynamically the DSS MLflow plugin:
        MLflow uses entrypoints==0.3 to load entrypoints from plugins at import time.
        We add dss-mlflow-plugin entrypoints dynamically by adding them in sys.path
        at call time.

        2. Setup the correct environment variables to setup the plugin to work
        with DSS backend as the tracking backend and enable using DSS managed folder
        as artifact location.
        """
        self.project = project
        self.project_key = project.project_key
        self.client = client
        self.mlflow_env = {}

        # Load DSS as the plugin
        self.tempdir = tempfile.mkdtemp()
        plugin_dir = os.path.join(self.tempdir, "dss-plugin-mlflow.egg-info")
        if not os.path.isdir(plugin_dir):
            os.makedirs(plugin_dir)
        with open(os.path.join(plugin_dir, "entry_points.txt"), "w") as f:
            f.write(
                "[mlflow.request_header_provider]\n"
                "unused=dataikuapi.dss_plugin_mlflow.header_provider:PluginDSSHeaderProvider\n"
                "[mlflow.artifact_repository]\n"
                "dss-managed-folder=dataikuapi.dss_plugin_mlflow.artifact_repository:PluginDSSManagedFolderArtifactRepository\n"
            )
        sys.path.insert(0, self.tempdir)

        # Reload the artifact_repository_registry in case MLflow was imported beforehand
        if sys.version_info > (3, 4):
            from importlib import reload
        import mlflow
        reload(mlflow.store.artifact.artifact_repository_registry)

        # Setup authentication
        if client._session.auth is not None:
            self.mlflow_env.update({
                "DSS_MLFLOW_HEADER": "Authorization",
                "DSS_MLFLOW_TOKEN": "Basic {}".format(
                    b64encode("{}:".format(self.client._session.auth.username).encode("utf-8")).decode("utf-8")),
                "DSS_MLFLOW_APIKEY": self.client.api_key
            })
        elif client.internal_ticket:
            self.mlflow_env.update({
                "DSS_MLFLOW_HEADER": "X-DKU-APITicket",
                "DSS_MLFLOW_TOKEN": self.client.internal_ticket,
                "DSS_MLFLOW_INTERNAL_TICKET": self.client.internal_ticket
            })

        if not isinstance(managed_folder, DSSManagedFolder):
            raise TypeError('managed_folder must a DSSManagedFolder.')

        if not client._session.verify:
            self.mlflow_env.update({"MLFLOW_TRACKING_INSECURE_TLS": "true"})
        elif isinstance(client._session.verify, str):
            self.mlflow_env.update({"MLFLOW_TRACKING_SERVER_CERT_PATH": client._session.verify})


        mf_project = managed_folder.project.project_key
        mf_id = managed_folder.id
        try:
            client.get_project(mf_project).get_managed_folder(mf_id).get_definition()
        except DataikuException as e:
            if "NotFoundException" in str(e):
                logging.error('The managed folder "%s" does not exist, please create it in your project flow before running this command.' % (mf_id))
            raise

        # Set host, tracking URI, project key and managed_folder_id
        self.mlflow_env.update({
            "DSS_MLFLOW_PROJECTKEY": self.project_key,
            "MLFLOW_TRACKING_URI": self.client.host + "/dip/publicapi" if host is None else host,
            "DSS_MLFLOW_HOST": self.client.host,
            "DSS_MLFLOW_MANAGED_FOLDER_ID": mf_project + "." + mf_id
        })

        os.environ.update(self.mlflow_env)

    def clear(self):
        shutil.rmtree(self.tempdir)
        for variable in self.mlflow_env:
            os.environ.pop(variable, None)

    def import_mlflow(self):
        import mlflow
        return mlflow

    def __enter__(self):
        return self.import_mlflow()

    def __exit__(self, exc_type, exc_value, traceback):
        self.clear()
