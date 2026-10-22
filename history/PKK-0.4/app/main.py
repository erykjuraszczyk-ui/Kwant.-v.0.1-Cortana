from fastapi import FastAPI, Query
from .models import ObservationBatch
from .world import WorldMemory

app = FastAPI(
    title="PKK — Percepcyjny Komputer Kwantowy",
    version="0.4.0",
    description="PKK 0.4: pamięć percepcyjna i prosty model świata. Klasyczny prototyp AI."
)
memory = WorldMemory()

@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}

@app.get("/version")
def version():
    return {"name": "PKK", "version": app.version, "stage": "perceptual-memory"}

@app.post("/perception/observations")
def ingest_observations(batch: ObservationBatch):
    return memory.ingest(batch)

@app.get("/world/state")
def world_state():
    return {"objects": memory.state(), "count": len(memory.objects)}

@app.get("/memory/events")
def memory_events(limit: int = Query(default=100, ge=1, le=500)):
    return {"events": memory.event_list(limit), "count": min(limit, len(memory.events))}

@app.post("/memory/reset")
def reset_memory():
    return memory.reset()
