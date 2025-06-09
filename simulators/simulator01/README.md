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

*   **Attention Harvesting:** Entities try to harvest a fixed amount; there's no complex model of attention sources or competition for specific sources. (Note: This is now influenced by the Acquisitiveness trait).
*   **Value Creation:** "Value" is an abstract counter incremented by processing. It doesn't represent tangible output or utility within the simulation itself. (Note: Amount of value is influenced by Calculation trait).
*   **Adaptation:** Adaptation is very basic (reducing processing cost). The rich adaptation strategies from the documentation are not implemented. (Note: Trait system provides another layer of behavioral modification).
*   **Reproduction & Mutation:** Reproduction creates copies. Offspring inherit the parent's trait scores and base behavioral parameters. There's no random mutation of traits or parameters during inheritance in this version.
*   **Niche Specialization:** Not implemented. All entities behave similarly based on their parameters, though traits now introduce significant behavioral variance.
*   **Environment Interaction:** Limited to harvesting global attention. No complex environmental factors or localized resources.
*   **No GUI:** Output is text-based to the console.

## Future Development Ideas

*   More sophisticated attention models (e.g., localized attention hotspots).
*   Diverse types of "information" and "value".
*   Advanced adaptation and evolution mechanisms (e.g., strategy changes, mutation of parameters during reproduction).
*   Niche differentiation and competition/cooperation between entities.
*   Data logging for analysis and visualization.
*   More complex interactions between traits.

## Trait System (New)

Entities now possess a system of traits that can influence their behavior. Traits are managed by a `TraitManager` within each entity.

### Initialization & Inheritance
*   Traits are scored on a scale from 0.0 to 1.0 (defaulting to 0.5 if unspecified).
*   When entities are initialized in `main.py`, they are assigned random scores for the currently implemented traits. Their base behavioral parameters (like base harvesting amount, base processing cost, etc.) are also randomized to create diversity.
*   When an entity reproduces, its offspring inherit the parent's exact trait scores and base behavioral parameters.

### Implemented Traits and Their Effects

The following traits are currently implemented:

1.  **Acquisitiveness:**
    *   **Effect:** Influences the amount of attention an entity attempts to harvest each cycle.
    *   **Mechanism:** The entity's base `harvest_amount` is multiplied by a factor derived from the Acquisitiveness score. A score of 0.0 results in a 0.5x multiplier, 0.5 results in a 1.0x multiplier (base amount), and 1.0 results in a 1.5x multiplier.

2.  **Cautiousness:**
    *   **Effect:** Makes entities more conservative with energy expenditure.
    *   **Mechanisms:**
        *   **Reproduction Threshold:** Increases the energy an entity needs before it considers reproducing. A score of 0.0 applies a 0.8x multiplier to the base threshold, 0.5 applies 1.0x, and 1.0 applies 1.2x.
        *   **Processing Safety Margin:** Requires an entity to have more energy relative to processing cost before it attempts to process information. The safety factor ranges from 1.0x (at trait 0.0, meaning energy must simply meet cost) to 1.5x (at trait 1.0, meaning energy must be 1.5 times the cost). A neutral 0.5 score results in a 1.25x safety factor.

3.  **RiskTaking:**
    *   **Effect:** Acts as a counter to Cautiousness, making entities bolder.
    *   **Mechanisms:**
        *   **Reproduction Threshold:** Modifies the Cautiousness-adjusted reproduction threshold. A RiskTaking score of 0.0 further increases the threshold (1.1x multiplier), 0.5 has no effect (1.0x), and 1.0 decreases it (0.9x multiplier).
        *   **Processing Safety Margin:** Modifies the Cautiousness-adjusted processing safety factor. A RiskTaking score of 0.0 further increases the safety factor (1.1x), 0.5 has no effect (1.0x), and 1.0 decreases it (0.9x).

4.  **Calculation (Processing Efficiency & Effectiveness):**
    *   **Effect:** Influences the efficiency of information processing.
    *   **Mechanisms:**
        *   **Processing Cost:** Modifies the base processing cost. A score of 0.0 results in a 1.2x cost multiplier (less efficient), 0.5 results in 1.0x, and 1.0 results in a 0.8x cost multiplier (more efficient). Minimum effective cost is 1.
        *   **Value Generated:** Modifies the base value generated per processing event. A score of 0.0 results in a 0.8x value multiplier, 0.5 results in 1.0x, and 1.0 results in a 1.2x value multiplier. Minimum effective value increment is 0.

5.  **Destructiveness (Metabolic Cost):**
    *   **Effect:** Influences the entity's passive energy drain (metabolic cost).
    *   **Mechanism:** Modifies the base energy cost per cycle. A score of 0.0 results in a 0.8x metabolic cost multiplier, 0.5 results in 1.0x, and 1.0 results in a 1.2x metabolic cost multiplier. Minimum effective cost is 0.

### Extensibility
The `TraitManager` is designed to be easily extensible. New traits can be added by:
1. Defining their names and default values.
2. Implementing logic within the relevant entity methods (`Attentiophage`, `CoreProcessor`, `EnergyManager`, `ReproductionManager`) to modify behavior based on the new trait scores.
