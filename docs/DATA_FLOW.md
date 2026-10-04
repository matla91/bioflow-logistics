# Smartflow data flow

Slide-ready colour diagram: [PNG, 3200 × 1800](slides/smartflow-data-flow.png) · [editable SVG, 16:9](slides/smartflow-data-flow.svg). The visual shows the product flow; its footer identifies the separate demo databases and batch-linked work still being integrated.

Shipment and manufacturing records enter from an ERP source; public signals enter through provider ingestion. The analysis worker reads stored inputs and writes versioned JSON assessments and evidence. Smartflow displays assessments alongside operational records. People approve or override recommendations, and the app stores their decision traces.

## Product flow

```mermaid
flowchart LR
    EXT["External signals<br/>Rhine levels · weather · traffic"]
    ING["Provider ingestion<br/>Collect, normalize and cache"]
    ERP["ERP / manufacturing systems<br/>Shipments · batches · inventory<br/>QA status · stock reservations<br/>Demo: synthetic operations generator"]
    SENSOR["Shipment sensor feed<br/>Demo: simulated temperature readings"]

    subgraph DATA["Smartflow data layer"]
        INPUT[("Operational inputs<br/>Public observations and ERP records")]
        RESULT[("Assessment JSON and evidence<br/>Input snapshot · model version · probabilities")]
        TRACE[("Human decision traces<br/>Assessment reference · actor · time<br/>Action · reason · approval or override")]
    end

    ML["ML / simulation engine<br/>Probabilities and supporting evidence<br/>Rules recommend an action"]
    READ["Read API<br/>Operational context and assessment results"]
    APP["Smartflow app<br/>Latest assessment and evidence<br/>Shipment and batch context"]
    HUMAN["Operator · QA · Logistics<br/>Review and decide"]

    EXT --> ING --> INPUT
    ERP -->|"Import operational records"| INPUT
    SENSOR --> INPUT
    INPUT -->|"Read inputs at analysis cutoff"| ML
    ML -->|"Append assessment JSON"| RESULT
    INPUT --> READ
    RESULT --> READ --> APP
    APP -->|"Recommendation and evidence"| HUMAN
    HUMAN -->|"Approve or override with reason"| APP
    APP -->|"Append human decision"| TRACE
    TRACE -->|"Decision history"| APP
```

The ERP box represents the intended business-system input. In the demo, a synthetic operations generator supplies linked shipments, batches, inventory, QA status and reservations. Simulated sensor readings represent a separate shipment telemetry feed. There is no live ERP connection yet.

Latest means the newest applicable assessment for the selected shipment or batch at the displayed cutoff, with its model version and evidence retained. A newer assessment must not change a previously recorded decision's assessment reference. The engine supplies probabilities and recommendations; a person records the decision.

## Current local implementation

```mermaid
flowchart LR
    PUBLIC["External signals / offline provider cache"] --> INGEST["Data collection and cache import"]
    FIXTURE["ERP stand-in<br/>Synthetic operations and sensor readings"] --> ENGINE_DB
    INGEST --> ENGINE_DB[("Engine SQLite<br/>Provider observations<br/>Operational records<br/>Immutable assessment JSON and evidence")]
    ENGINE_DB -->|"Read observations and linked operations at cutoff"| WORKER["Named logistics / batch analysis worker"]
    WORKER -->|"Persist inputs and results"| ENGINE_DB
    ENGINE_DB --> API["FastAPI read service<br/>localhost:8002"]
    API --> APP["Laravel Smartflow app<br/>localhost:8000<br/>Integration view and shipment console"]
    APP -->|"Record human decisions"| APP_DB[("Laravel SQLite<br/>Shipment console records<br/>Decision traces")]
    APP_DB -->|"Read console and decision history"| APP
```

The two SQLite databases are separate physical stores. Laravel reads the engine through HTTP and manages its own tables; its migrations must not target the engine database. The integration view lists three named logistics scenario assessments and operational dataset counts. The [batch worker and API](BATCH_ASSESSMENTS.md) serve linked immutable results in `/integration/batches`: Laravel fetches the stored list and selected batch's latest record; Vue formats the generated contract without recomputing decisions. Production reservations, incoming shipment timing and sampled product-temperature/QA evidence have separate cards. The existing shipment console reads Laravel records and writes its decision traces there; the batch view is read-only. The [named-scenario decision step](INTEGRATION_DECISIONS.md) separately records human choices by external Python assessment hash in Laravel, without shipment-console linkage or writes to the engine database.

The [ML brief](implementation-ml.md) adds batch-linked assessments using stored operational inputs. The [Laravel brief](implementation-laravel.md) adds linked operational imports, batch views, latest applicable assessment display and decisions tied to assessment evidence. These complete the product flow above without combining the databases.
