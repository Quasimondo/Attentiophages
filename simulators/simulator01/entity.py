class EnergyManager:
    """Manages the energy of an entity."""

    def __init__(self, initial_energy=100, max_energy=200, energy_per_cycle=1):
        """
        Initializes the EnergyManager.

        Args:
            initial_energy (int): The starting energy level.
            max_energy (int): The maximum energy level.
            energy_per_cycle (int): The energy cost per simulation cycle.
        """
        self.current_energy = initial_energy
        self.max_energy = max_energy
        self.energy_per_cycle = energy_per_cycle

    def gain_energy(self, amount):
        """
        Increases current energy by the given amount, up to max_energy.

        Args:
            amount (int): The amount of energy to gain.
        """
        self.current_energy = min(self.max_energy, self.current_energy + amount)

    def lose_energy(self, amount):
        """
        Decreases current energy by the given amount.

        Args:
            amount (int): The amount of energy to lose.

        Returns:
            bool: True if energy drops to 0 or below, False otherwise.
        """
        self.current_energy -= amount
        return self.current_energy <= 0

    def metabolic_cost(self):
        """
        Decreases current energy by the energy_per_cycle.

        Returns:
            bool: True if energy drops to 0 or below, False otherwise.
        """
        return self.lose_energy(self.energy_per_cycle)


class CoreProcessor:
    """Handles information processing for an entity."""

    def __init__(self, processing_cost=10):
        """
        Initializes the CoreProcessor.

        Args:
            processing_cost (int): The energy cost to process information.
        """
        self.processing_cost = processing_cost
        self.value_generated = 0

    def process_information(self, energy_manager):
        """
        Processes information if there is enough energy.

        Args:
            energy_manager (EnergyManager): The entity's energy manager.

        Returns:
            bool: True if processing was successful, False otherwise.
        """
        if energy_manager.current_energy >= self.processing_cost:
            energy_manager.lose_energy(self.processing_cost)
            self.value_generated += 5
            return True
        return False


class AdaptationEngine:
    """Handles adaptation mechanisms for an entity."""

    def __init__(self, adaptation_threshold=50):
        """
        Initializes the AdaptationEngine.

        Args:
            adaptation_threshold (int): The energy level below which adaptation might occur.
        """
        self.adaptation_threshold = adaptation_threshold

    def adapt(self, energy_manager, core_processor):
        """
        Adapts the entity's properties based on its energy level.

        Args:
            energy_manager (EnergyManager): The entity's energy manager.
            core_processor (CoreProcessor): The entity's core processor.
        """
        if energy_manager.current_energy < self.adaptation_threshold:
            if core_processor.processing_cost > 1:
                core_processor.processing_cost = max(1, core_processor.processing_cost - 1)
                print(f"Adapting: Reduced processing cost to {core_processor.processing_cost}")


class ReproductionManager:
    """Manages the reproduction process for an entity."""

    def __init__(self, reproduction_cost=50, energy_threshold_for_reproduction=150):
        """
        Initializes the ReproductionManager.

        Args:
            reproduction_cost (int): The energy cost to reproduce.
            energy_threshold_for_reproduction (int): The minimum energy required to reproduce.
        """
        self.reproduction_cost = reproduction_cost
        self.energy_threshold_for_reproduction = energy_threshold_for_reproduction

    def should_reproduce(self, current_energy):
        """
        Checks if the entity has enough energy to consider reproduction.

        Args:
            current_energy (int): The current energy of the entity.

        Returns:
            bool: True if energy is above or equal to the threshold, False otherwise.
        """
        return current_energy >= self.energy_threshold_for_reproduction

    def reproduce(self, energy_manager, entity_id_str):
        """
        Attempts to deduct energy for reproduction if conditions are met.

        Args:
            energy_manager (EnergyManager): The energy manager of the entity.
            entity_id_str (str): The string representation of the entity's ID for logging.

        Returns:
            bool: True if reproduction cost was successfully deducted, False otherwise.
        """
        if self.should_reproduce(energy_manager.current_energy):
            if energy_manager.current_energy >= self.reproduction_cost:
                 energy_manager.lose_energy(self.reproduction_cost)
                 print(f"Entity {entity_id_str} reproductive systems active (energy cost deducted).")
                 return True
        return False


class Attentiophage:
    """Represents an Attentiophage entity in the simulation."""

    def __init__(self, entity_id, initial_energy=100, max_energy=200, energy_per_cycle=1, processing_cost=10, harvest_amount=20, reproduction_cost=50, energy_threshold_for_reproduction=150, **kwargs):
        """
        Initializes an Attentiophage.

        Args:
            entity_id (str): A unique identifier for the entity.
            initial_energy (int): The starting energy level.
            max_energy (int): The maximum energy level.
            energy_per_cycle (int): The energy cost per simulation cycle.
            processing_cost (int): The energy cost for the core processor.
            harvest_amount (int): The amount of energy the entity attempts to harvest.
            reproduction_cost (int): The energy cost for reproduction.
            energy_threshold_for_reproduction (int): The energy level needed to reproduce.
            **kwargs: Additional keyword arguments.
        """
        self.entity_id = entity_id
        self.energy_manager = EnergyManager(initial_energy, max_energy, energy_per_cycle)
        self.core_processor = CoreProcessor(processing_cost)
        self.harvest_amount = harvest_amount
        self.adaptation_engine = AdaptationEngine()  # Default adaptation_threshold
        self.is_alive = True
        self.reproduction_manager = ReproductionManager(reproduction_cost, energy_threshold_for_reproduction)

    def perform_cycle_actions(self, environment):
        """
        Performs the actions for one simulation cycle.

        Args:
            environment (Environment): The environment in which the entity exists.
        """
        if not self.is_alive:
            return

        # Attempt to harvest attention
        harvested_energy = environment.provide_attention(self.harvest_amount)
        self.energy_manager.gain_energy(harvested_energy)
        # Optional: print(f"Entity {self.entity_id} harvested {harvested_energy} energy.")

        self.core_processor.process_information(self.energy_manager)
        self.adaptation_engine.adapt(self.energy_manager, self.core_processor)

        # Attempt reproduction
        # Check should_reproduce first to avoid unnecessary calls if obvious not enough energy
        if self.reproduction_manager.should_reproduce(self.energy_manager.current_energy):
            # The reproduce method now only deducts energy and signals success
            if self.reproduction_manager.reproduce(self.energy_manager, str(self.entity_id)):
                # If energy was deducted, then ask environment to spawn offspring
                offspring_config = {
                    "initial_energy": self.energy_manager.max_energy // 2, # Start with decent energy
                    "max_energy": self.energy_manager.max_energy,
                    "energy_per_cycle": self.energy_manager.energy_per_cycle,
                    "processing_cost": self.core_processor.processing_cost,
                    "harvest_amount": self.harvest_amount,
                    "reproduction_cost": self.reproduction_manager.reproduction_cost,
                    "energy_threshold_for_reproduction": self.reproduction_manager.energy_threshold_for_reproduction
                }
                environment.add_offspring(offspring_config)

        if self.energy_manager.metabolic_cost():
            self.is_alive = False
            print(f"Entity {self.entity_id} has run out of energy.")
