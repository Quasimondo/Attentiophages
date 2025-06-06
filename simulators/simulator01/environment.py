from .entity import Attentiophage # Add this import at the top of the file

class Environment:
    """Manages the simulation environment, entities, and attention resources."""

    def __init__(self, initial_attention_units=1000, attention_units_per_step=50, max_entities=50):
        """
        Initializes the Environment.

        Args:
            initial_attention_units (int): The starting amount of available attention.
            attention_units_per_step (int): Amount of attention regenerated each step.
            max_entities (int): The maximum number of entities allowed in the environment.
        """
        self.entities = {}  # entity_id: Attentiophage object
        self.available_attention_units = initial_attention_units
        self.attention_units_per_step = attention_units_per_step
        self.current_step = 0
        self.next_entity_id = 0
        self.max_entities = max_entities

    def add_entity(self, entity):
        """
        Adds an entity to the environment.

        Args:
            entity (Attentiophage): The entity to add.
        """
        entity.entity_id = self.next_entity_id
        self.entities[self.next_entity_id] = entity
        print(f"Entity {self.next_entity_id} added to environment.")
        self.next_entity_id += 1


    def remove_entity(self, entity_id):
        """
        Removes an entity from the environment.

        Args:
            entity_id (int): The ID of the entity to remove.
        """
        if entity_id in self.entities:
            del self.entities[entity_id]
            print(f"Entity {entity_id} removed from environment.")
        else:
            print(f"Entity {entity_id} not found in environment for removal.")


    def provide_attention(self, requested_amount):
        """
        Provides a requested amount of attention if available.

        Args:
            requested_amount (int): The amount of attention requested.

        Returns:
            int: The amount of attention actually provided.
        """
        if self.available_attention_units >= requested_amount:
            self.available_attention_units -= requested_amount
            return requested_amount
        elif self.available_attention_units > 0:
            amount_to_give = self.available_attention_units
            self.available_attention_units = 0
            return amount_to_give
        else:
            return 0

    def regenerate_attention(self):
        """Increases available attention by the configured amount per step."""
        self.available_attention_units += self.attention_units_per_step

    def simulation_step(self):
        """Performs one step of the simulation."""
        self.current_step += 1
        self.regenerate_attention()

        # Iterate over a copy of entity IDs for safe removal
        for entity_id in list(self.entities.keys()):
            entity = self.entities.get(entity_id) # Get entity in case it was removed in this loop by another
            if not entity:
                continue

            if entity.is_alive:
                entity.perform_cycle_actions(self)
                # Future: Interaction for harvesting attention will be added here.

            # Check entity status again as perform_cycle_actions might change it
            if not entity.is_alive:
                self.remove_entity(entity.entity_id)

        print(
            f"Step {self.current_step} complete. "
            f"Entities: {len(self.entities)}. "
            f"Attention: {self.available_attention_units}."
        )

    def add_offspring(self, offspring_config):
        """Creates and adds a new Attentiophage (offspring) to the environment if not exceeding max_entities."""
        if len(self.entities) < self.max_entities:
            # Create the new Attentiophage instance using parameters from offspring_config
            new_entity = Attentiophage(
                entity_id=None, # Will be set by self.add_entity
                initial_energy=offspring_config.get("initial_energy", 50),
                max_energy=offspring_config.get("max_energy", 200),
                energy_per_cycle=offspring_config.get("energy_per_cycle", 1),
                processing_cost=offspring_config.get("processing_cost", 10),
                harvest_amount=offspring_config.get("harvest_amount", 20),
                reproduction_cost=offspring_config.get("reproduction_cost", 50),
                energy_threshold_for_reproduction=offspring_config.get("energy_threshold_for_reproduction", 150)
            )
            self.add_entity(new_entity)
            print(f"New offspring Entity {new_entity.entity_id} added. Total entities: {len(self.entities)}")
        else:
            print(f"Environment at maximum capacity ({self.max_entities}). Offspring not added.")
