from datetime import datetime, timedelta, timezone

import jsonpickle
import pytest
from airflow.operators.python import PythonOperator
from airflow.sensors.bash import BashSensor
from airflow.sensors.time_sensor import TimeSensor
from flyteidl.core.execution_pb2 import TaskExecution
from flytekitplugins.airflow import AirflowObj
from flytekitplugins.airflow.connector import AirflowConnector, AirflowMetadata

from flytekit import workflow
from flytekit.interfaces.cli_identifiers import Identifier
from flytekit.models import interface as interface_models
from flytekit.models import literals, task
from flytekit.models.core.identifier import ResourceType
from flytekit.models.task import TaskTemplate


def py_func():
    print("airflow python sensor")
    return True


@workflow
def wf():
    sensor = TimeSensor(
        task_id="fire_immediately", target_time=(datetime.now(tz=timezone.utc) + timedelta(seconds=1)).time()
    )
    t3 = BashSensor(task_id="Sensor_succeeds", bash_command="exit 0")
    foo = PythonOperator(task_id="foo", python_callable=py_func)
    sensor >> t3 >> foo


def test_airflow_workflow():
    wf()


def test_resource_metadata():
    task_cfg = AirflowObj(
        module="airflow.operators.bash",
        name="BashOperator",
        parameters={"task_id": "id", "bash_command": "echo 'hello world'"},
    )
    trigger_cfg = AirflowObj(module="airflow.trigger.file", name="FileTrigger", parameters={"filepath": "file.txt"})
    meta = AirflowMetadata(
        airflow_operator=task_cfg,
        airflow_trigger=trigger_cfg,
        airflow_trigger_callback="execute_complete",
        job_id="123",
    )
    assert meta.airflow_operator == task_cfg
    assert meta.airflow_trigger == trigger_cfg
    assert meta.airflow_trigger_callback == "execute_complete"
    assert meta.job_id == "123"


@pytest.mark.asyncio
async def test_airflow_connector():
    cfg = AirflowObj(
        module="airflow.operators.bash",
        name="BashOperator",
        parameters={"task_id": "id", "bash_command": "echo 'hello world'"},
    )
    task_id = Identifier(
        resource_type=ResourceType.TASK, project="project", domain="domain", name="airflow_Task", version="version"
    )
    task_metadata = task.TaskMetadata(
        True,
        task.RuntimeMetadata(task.RuntimeMetadata.RuntimeType.FLYTE_SDK, "1.0.0", "python"),
        timedelta(days=1),
        literals.RetryStrategy(3),
        True,
        "0.1.1b0",
        "This is deprecated!",
        True,
        "A",
        None
    )

    interfaces = interface_models.TypedInterface(inputs={}, outputs={})

    dummy_template = TaskTemplate(
        id=task_id,
        metadata=task_metadata,
        interface=interfaces,
        type="airflow",
        custom={"task_config_pkl": jsonpickle.encode(cfg)},
    )

    connector = AirflowConnector()
    metadata = await connector.create(dummy_template, None)
    resource = await connector.get(metadata)
    assert resource.phase == TaskExecution.SUCCEEDED
    assert resource.message is None
    res = await connector.delete(metadata)
    assert res is None
