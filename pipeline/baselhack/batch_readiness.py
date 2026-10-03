"""Conserved batch material quantities from released reservations and supply plans."""

from baselhack.interfaces import BatchStockEvidence, ProductionReadiness


def production_readiness(snapshot):
    """Credit only this batch's released reservations, never competing/free stock."""
    evidence = []
    eligible_by_lot = {}
    for lot in snapshot.inventory:
        reservations = [
            r for r in snapshot.reservations if r.inventory_lot_id == lot.id
        ]
        own = sum(
            r.quantity_kg for r in reservations if r.batch_id == snapshot.batch.id
        )
        others = sum(
            r.quantity_kg for r in reservations if r.batch_id != snapshot.batch.id
        )
        if own + others > lot.quantity_kg + 1e-9:
            raise ValueError("Reservations exceed inventory quantity")
        reason = (
            "Released stock reserved to this batch is available by the charge time."
        )
        eligible = own
        if snapshot.reference_at > snapshot.as_of:
            eligible, reason = (
                0,
                "Snapshot postdates cutoff; historical QA/reservations are unknown.",
            )
        elif lot.qa_status != "released":
            eligible, reason = (
                0,
                "Pending-QA or quarantined stock is not released material.",
            )
        elif lot.available_at > min(snapshot.as_of, snapshot.batch.planned_charge_at):
            eligible, reason = (
                0,
                "Stock is unavailable at cutoff or planned charge time.",
            )
        elif not own:
            reason = "Stock is unreserved or reserved to another batch; no coverage credited."
        if eligible and snapshot.batch.planned_charge_at <= snapshot.as_of:
            reason = (
                "The current operational snapshot contains released stock reserved "
                "to this batch, with an availability timestamp at or before charge. "
                "Historical reservation/QA state at the exact charge time cannot "
                "be reconstructed from this snapshot."
            )
        eligible_by_lot[lot.id] = eligible
        evidence.append(
            BatchStockEvidence(
                inventory_lot_id=lot.id,
                quantity_kg=lot.quantity_kg,
                reserved_for_batch_kg=own,
                reserved_for_others_kg=others,
                unreserved_quantity_kg=max(lot.quantity_kg - own - others, 0),
                eligible_reserved_quantity_kg=eligible,
                qa_status=lot.qa_status,
                available_at=lot.available_at,
                reason=reason,
            )
        )
    reserved = sum(eligible_by_lot.values())
    demand = snapshot.batch.required_quantity_kg
    if reserved > demand + 1e-9:
        raise ValueError("Reservations exceed batch demand")
    shortfall = max(demand - reserved, 0)
    remaining = shortfall
    dependencies = {}
    shipments = {s.id: s for s in snapshot.shipments}
    released_deliveries = {
        lot.id for lot in snapshot.inventory if lot.qa_status == "released"
    }
    for plan in snapshot.supply_plans:
        # Delivered released stock must be allocated via reservations. Counting its
        # original incoming plan again could steal a competing batch's reservation.
        available_plan = (
            0
            if shipments[plan.shipment_id].lot_id in released_deliveries
            else plan.quantity_kg
        )
        dependencies[plan.shipment_id] = min(remaining, available_plan)
        remaining = max(remaining - dependencies[plan.shipment_id], 0)
    readiness = ProductionReadiness(
        planned_charge_at=snapshot.batch.planned_charge_at,
        required_quantity_kg=demand,
        released_reserved_quantity_kg=reserved,
        reservation_shortfall_kg=shortfall,
        incoming_dependency_kg=shortfall - remaining,
        uncovered_quantity_kg=remaining,
        status=(
            "RESERVED_STOCK_SUFFICIENT"
            if shortfall == 0
            else "INCOMING_DEPENDENT"
            if remaining == 0
            else "INSUFFICIENT_SUPPLY"
        ),
        stock_evidence=evidence,
    )
    return readiness, dependencies
