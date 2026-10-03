def traffic_factor(scenario, at):
    return scenario["traffic"]["factor_by_hour"].get(
        at.strftime("%H"), scenario["thresholds"]["traffic_default_factor"]
    )
