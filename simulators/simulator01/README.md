# Attentiophage Simulator 01

This project is a basic Python-based simulation of the Attentiophage concept, as described in the parent repository's documentation. It models digital entities (Attentiophages) that interact with an environment, consume "attention" as energy, process information to create value, adapt, and reproduce.

## Core Concepts Simulated

*   **Attentiophages (Entities):** Each entity has:
    *   An `EnergyManager` to handle energy levels (gained from attention, lost via metabolism and processing).
    *   A `CoreProcessor` that consumes energy to "process information" and generate "value".
    *   An `AdaptationEngine` for basic behavioral changes (e.g., reducing processing cost when energy is low).
    *   A `ReproductionManager` to handle reproduction if energy thresholds and costs are met.
    *   A defined `harvest_amount` determining how much attention it tries to get per cycle.
*   **Environment:**
    *   Manages a population of Attentiophages.
    *   Contains "attention units" as a global resource.
    *   Regenerates a fixed amount of attention each simulation step.
    *   Has a maximum capacity for entities.
*   **Simulation Loop:**
    *   Discrete time steps.
    *   In each step:
        1.  Environment regenerates attention.
        2.  Each Attentiophage attempts to:
            *   Harvest attention from the environment.
            *   Process information (costing energy, generating value).
            *   Adapt if conditions are met (e.g., low energy).
            *   Reproduce if conditions are met (costing energy, potentially creating offspring if environment capacity allows).
            *   Pay metabolic energy cost.
        3.  Entities that run out of energy are removed from the simulation.

## How to Run

1.  Navigate to the root directory of the repository.
2.  Ensure you have Python 3 installed.
3.  Run the simulator directly using:
    ```bash
    python -m simulators.simulator01.main
    ```
    This will execute the `run_simulation` function in `main.py` with default parameters.

## Current Limitations & Simplifications

This is a foundational simulation and has several simplifications:

*   **Attention Harvesting:** Entities try to harvest a fixed amount; there's no complex model of attention sources or competition for specific sources.
*   **Value Creation:** "Value" is an abstract counter incremented by processing. It doesn't represent tangible output or utility within the simulation itself.
*   **Adaptation:** Adaptation is very basic (reducing processing cost). The rich adaptation strategies from the documentation are not implemented.
*   **Reproduction & Mutation:** Reproduction creates copies with slightly varied initial energy. There's no genetic inheritance or mutation of traits beyond initial configuration.
*   **Niche Specialization:** Not implemented. All entities behave similarly based on their parameters.
*   **Environment Interaction:** Limited to harvesting global attention. No complex environmental factors or localized resources.
*   **No GUI:** Output is text-based to the console.

## Future Development Ideas

*   More sophisticated attention models (e.g., localized attention hotspots).
*   Diverse types of "information" and "value".
*   Advanced adaptation and evolution mechanisms (e.g., strategy changes, mutation of parameters).
*   Niche differentiation and competition/cooperation between entities.
*   Data logging for analysis and visualization.
