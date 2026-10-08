"""Architecture diagram for the Tesla driving-data MLOps project.

Extends saranreddy/sagemaker-mlops-pipeline-starter (pipeline, registry, deploy_model.py)
and saranreddy/sagemaker-model-monitor-starter (data capture, baseline, scheduled checks)
to predict a drive's energy use (Wh/mi) from the owner's own TeslaMate data.

Style mirrors docs/architecture.py in the starter repo (same fonts, palette, edge styles).

Render:  pip install diagrams   (also needs Graphviz: apt install graphviz / brew install graphviz)
         python docs/architecture.py  ->  docs/architecture.png (next to this script)
"""
import os

from diagrams import Cluster, Diagram, Edge, getdiagram
from diagrams.aws.analytics import Athena, GlueDataCatalog, KinesisDataFirehose, KinesisDataStreams
from diagrams.aws.compute import EC2, Fargate, Lambda
from diagrams.aws.general import User
from diagrams.aws.integration import EventbridgeScheduler, SNS
from diagrams.aws.iot import IotCar
from diagrams.aws.management import CloudwatchAlarm
from diagrams.aws.ml import Sagemaker, SagemakerModel, SagemakerTrainingJob
from diagrams.aws.network import APIGateway
from diagrams.aws.storage import SimpleStorageServiceS3Bucket
from diagrams.onprem.database import Postgresql
from diagrams.onprem.iac import Terraform
from diagrams.onprem.monitoring import Grafana
from diagrams.onprem.network import Internet
from diagrams.programming.flowchart import Decision
from diagrams.programming.language import Python

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "architecture")

FONT = "DejaVu Sans"
GRAPH = {
    "fontname": FONT, "fontsize": "34", "labelloc": "t", "pad": "0.8",
    "nodesep": "0.55", "ranksep": "1.1", "splines": "spline", "newrank": "true",
    "compound": "true", "forcelabels": "true", "dpi": "170",
}
NODE = {"fontname": FONT, "fontsize": "21", "imagepos": "tc"}
EDGE = {"fontname": FONT, "fontsize": "19", "color": "#555555",
        "tailport": "e", "headport": "w"}

Edge._default_edge_attrs = {"fontcolor": "#2D3436", "fontname": FONT, "fontsize": "19"}


def box(bg, pen, style="rounded"):
    return {"bgcolor": bg, "pencolor": pen, "fontname": FONT, "fontsize": "21",
            "style": style, "labeljust": "l", "margin": "24"}


TF_BOX = box("#fff4e0", "#e66100")
INGEST_BOX = box("#fffaf2", "#e66100")
RUN_BOX = box("#e8f1fb", "#1a5fb4")
EXEC_BOX = box("#f3eefa", "#613583")
MON_BOX = box("#eef8f1", "#26a269")
MANAGED_BOX = box("#f6f5f4", "#9a9996", "dashed")
PHASE2_BOX = box("#fbf6f1", "#b5835a", "dashed,rounded")

FLOW = dict(color="#1a5fb4", fontcolor="#1a5fb4", penwidth="2.2")
IO = dict(color="#26a269", fontcolor="#1e7d4f", penwidth="1.8")
AUX = dict(color="#8a8a8a", fontcolor="#5e5c64", style="dotted", penwidth="1.8")
SETUP = dict(color="#e66100", fontcolor="#c64600", style="dashed", penwidth="1.8")
MANUAL = dict(color="#26a269", fontcolor="#1e7d4f", style="dashed", penwidth="2.2")
ALERT = dict(color="#c01c28", fontcolor="#c01c28", penwidth="2.2")
PHASE2 = dict(color="#b5835a", fontcolor="#8f5f3a", style="dashed", penwidth="2.4")
HIDDEN = dict(style="invis")
DOWN = dict(tailport="s", headport="n")
ROW = dict(tailport="e", headport="w")


def down(upper, lower, **attrs):
    """Vertical arrow upper -> lower between two nodes stacked in the same LR rank."""
    attrs = {**Edge._default_edge_attrs, "tailport": "_", "headport": "_", **attrs, "dir": "back"}
    getdiagram().dot.edge(lower._id, upper._id, **attrs)


class RawNode:
    def __init__(self, node_id):
        self._id = node_id


def same_rank(*nodes):
    getdiagram().dot.body.append("{rank=same; " + " ".join(f'"{n._id}";' for n in nodes) + "}")


with Diagram(
    "Tesla Driving Data MLOps on AWS",
    filename=OUT, outformat="png", show=False, direction="LR",
    graph_attr=GRAPH, node_attr=NODE, edge_attr=EDGE,
):
    car = IotCar("Tesla Model\n(your car)")
    tf = Terraform("terraform apply\n(infra/)")

    with Cluster("Tesla cloud (external)", graph_attr=MANAGED_BOX):
        tesla_api = Internet("Tesla Owner API")

    client = User("Trip estimate\nclient")

    with Cluster("AWS account  (us-east-1)  -  all infra Terraform-managed", graph_attr=TF_BOX) as acct:

        with Cluster("EC2 t4g.small  -  Docker: TeslaMate host", graph_attr=INGEST_BOX):
            teslamate = EC2("TeslaMate\n(poll + stream)")
            pg = Postgresql("PostgreSQL\ndrives + charges")
            grafana = Grafana("Grafana\nlive dashboards")
            export = Python("export_parquet.py\n(nightly cron)")

        with Cluster("Phase 2: official streaming", graph_attr=PHASE2_BOX):
            fleet = Fargate("Fleet Telemetry\nserver\n(ECS Fargate)")
            kds = KinesisDataStreams("Kinesis\nData Streams")
            firehose = KinesisDataFirehose("Data Firehose\n(to Parquet)")

        with Cluster("Data lake", graph_attr=INGEST_BOX):
            raw = SimpleStorageServiceS3Bucket("S3 raw zone\nParquet: drives,\ncharges")
            glue = GlueDataCatalog("Glue Data\nCatalog")
            athena = Athena("Athena\n(exploration)")

        sched = EventbridgeScheduler("EventBridge\nScheduler (weekly)")

        with Cluster("SageMaker Pipeline", graph_attr=EXEC_BOX) as pipeline:
            feat = Sagemaker("Feature engineering\n(Processing)")
            train = SagemakerTrainingJob("Train\nXGBoost")
            evaluate = Sagemaker("Evaluate\nevaluation.json")
            gate = Decision("Condition\nRMSE <= threshold\nelse: no model")
            register = SagemakerModel("Register\nModel Registry\n(manual approval)")

        with Cluster("Serving", graph_attr=RUN_BOX):
            apigw = APIGateway("API Gateway")
            fn = Lambda("Lambda\ntrip estimate")
            endpoint = Sagemaker("Real-time endpoint\nWh/mi prediction")
            deploy = Python("deploy_model.py\n(on approval)")

        with Cluster("Monitoring", graph_attr=MON_BOX):
            capture = SimpleStorageServiceS3Bucket("S3 data capture\nrequests +\npredictions")
            monitor = Sagemaker("Model Monitor\nbaseline + scheduled\ndata-quality / drift")
            alarm = CloudwatchAlarm("CloudWatch\nalarm")
            sns = SNS("SNS topic")

    owner = User("You\n(email)")

    down(grafana, export, style="invis")

    legend = (
        '<<TABLE BORDER="1" COLOR="#9a9996" CELLBORDER="0" CELLSPACING="2" CELLPADDING="5" BGCOLOR="#ffffff">'
        '<TR><TD COLSPAN="2" ALIGN="LEFT"><B>Legend</B></TD></TR>'
        '<TR><TD><FONT COLOR="#1a5fb4">&#9472;&#9472;&#9472;&#9654;</FONT></TD><TD ALIGN="LEFT">Phase 1 data / control flow</TD></TR>'
        '<TR><TD><FONT COLOR="#26a269">&#9472;&#9472;&#9472;&#9654;</FONT></TD><TD ALIGN="LEFT">data written / read</TD></TR>'
        '<TR><TD><FONT COLOR="#b5835a">- - - &#9654;</FONT></TD><TD ALIGN="LEFT">Phase 2 (planned)</TD></TR>'
        '<TR><TD><FONT COLOR="#8a8a8a">&#183; &#183; &#183; &#9654;</FONT></TD><TD ALIGN="LEFT">exploration / dashboards</TD></TR>'
        '<TR><TD><FONT COLOR="#c01c28">&#9472;&#9472;&#9472;&#9654;</FONT></TD><TD ALIGN="LEFT">drift alerting</TD></TR>'
        '</TABLE>>'
    )
    getdiagram().dot.node("legend", label=legend, shape="plaintext", fontname=FONT, fontsize="19", margin="0",
                         fixedsize="false", width="0", height="0", imagepos="mc")
    getdiagram().dot.body.append('{rank=same; "%s"; "legend";}' % owner._id)
    down(owner, RawNode("legend"), style="invis")

    same_rank(car, tf)
    same_rank(tesla_api, fleet)
    same_rank(teslamate, pg, kds)
    same_rank(grafana, export, firehose)
    same_rank(sched, raw, glue, athena)
    same_rank(feat, train, evaluate, gate, register)
    same_rank(client, apigw, fn, endpoint, deploy)
    same_rank(capture, monitor, alarm, sns)

    car >> Edge(xlabel="drives,\ncharges", **FLOW) >> tesla_api
    tesla_api >> Edge(**FLOW) >> teslamate
    down(teslamate, pg, **FLOW)
    pg >> Edge(**FLOW) >> export
    pg >> Edge(label="dashboards", **AUX) >> grafana
    export >> Edge(label="nightly\nParquet", **IO) >> raw
    down(raw, glue, **AUX)
    down(glue, athena, **AUX)

    car >> Edge(xlabel="Fleet Telemetry\n(mTLS)", **PHASE2) >> fleet
    fleet >> Edge(**PHASE2) >> kds
    kds >> Edge(**PHASE2) >> firehose
    firehose >> Edge(**PHASE2) >> raw

    raw >> Edge(label="raw drives", **IO) >> feat
    feat >> Edge(label="start\npipeline", **FLOW) >> train
    sched >> Edge(lhead=pipeline.name, **FLOW) >> feat
    down(feat, train, **FLOW)
    down(train, evaluate, **FLOW)
    down(evaluate, gate, **FLOW)
    down(gate, register, xlabel="pass", **MANUAL)

    register >> Edge(label="approved", **MANUAL) >> deploy
    down(client, apigw, **FLOW)
    down(apigw, fn, **FLOW)
    down(fn, endpoint, xlabel="invoke", **FLOW)
    deploy >> Edge(label="deploy", tailport="e", headport="e", **FLOW) >> endpoint
    endpoint >> Edge(label="data capture", **IO) >> capture

    down(capture, monitor, **IO)
    down(monitor, alarm, xlabel="violations", **ALERT)
    down(alarm, sns, **ALERT)
    sns >> Edge(label="email", **ALERT) >> owner

    tf >> Edge(label="provisions", lhead=acct.name, **SETUP) >> fleet
