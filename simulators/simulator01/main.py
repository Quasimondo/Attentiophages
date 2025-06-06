from .environment import Environment
from .entity import Attentiophage

def run_simulation(num_steps=100, initial_entities=5):
    """
    Sets up and runs the Attentiophage simulation.
    """
    print("--- Initializing Simulation ---")
    env = Environment(initial_attention_units=1000, attention_units_per_step=100, max_entities=50)

    for i in range(initial_entities):
        # Vary initial parameters slightly for diversity if desired, or keep them simple
        entity = Attentiophage(
            entity_id=None, # Will be set by env.add_entity
            initial_energy=100,
            max_energy=200,
            energy_per_cycle=2, # Slightly higher cost
            processing_cost=10,
            harvest_amount=25, # Slightly better harvest
            reproduction_cost=60,
            energy_threshold_for_reproduction=160
        )
        env.add_entity(entity)

    print(f"Initialized environment with {len(env.entities)} entities.")
    print(f"Initial available attention: {env.available_attention_units} units.")
    print("--- Starting Simulation Loop ---")

    for step in range(num_steps):
        print(f"--- Step {step + 1}/{num_steps} ---")
        env.simulation_step() # This method already prints some status

        # Gather additional stats for this step
        total_value_generated_this_step = 0 # This will be cumulative from all entities
        current_entity_count = len(env.entities)
        total_energy_this_step = 0

        if current_entity_count > 0:
            for entity_obj in env.entities.values(): # Renamed to avoid conflict with entity module
                total_value_generated_this_step += entity_obj.core_processor.value_generated
                total_energy_this_step += entity_obj.energy_manager.current_energy
            average_energy = total_energy_this_step / current_entity_count
            print(f"Entities: {current_entity_count}, Avg Energy: {average_energy:.2f}, Total Value (Cumulative): {total_value_generated_this_step}, Env Attention: {env.available_attention_units}")
        else:
            print("No entities remaining.")
            break # Stop simulation if no entities left

    print("--- Simulation Ended ---")
    # Final summary
    final_entity_count = len(env.entities)
    print(f"Final entity count: {final_entity_count}")
    if final_entity_count > 0:
        final_total_value = sum(e.core_processor.value_generated for e in env.entities.values())
        final_avg_energy = sum(e.energy_manager.current_energy for e in env.entities.values()) / final_entity_count
        print(f"Final average energy: {final_avg_energy:.2f}")
        print(f"Final total value generated (cumulative): {final_total_value}")
    print(f"Final available attention in environment: {env.available_attention_units}")

if __name__ == "__main__":
    run_simulation(num_steps=50, initial_entities=3) # Run for 50 steps with 3 initial entities
