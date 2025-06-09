import random # Added import
from .environment import Environment
from .entity import Attentiophage

def run_simulation(num_steps=100, initial_entities=5):
    """
    Sets up and runs the Attentiophage simulation.
    """
    print("--- Initializing Simulation ---")
    env = Environment(initial_attention_units=1000, attention_units_per_step=100, max_entities=50)

    for i in range(initial_entities):
        traits = {
            "Acquisitiveness": round(random.uniform(0.0, 1.0), 2),
            "Cautiousness": round(random.uniform(0.0, 1.0), 2),
            "RiskTaking": round(random.uniform(0.0, 1.0), 2),
            "Calculation": round(random.uniform(0.0, 1.0), 2),
            "Destructiveness": round(random.uniform(0.0, 1.0), 2)
        }
        entity = Attentiophage(
            entity_id=None,
            initial_energy=random.randint(80, 120), # Add some randomness to initial state
            max_energy=200,
            base_energy_per_cycle=random.randint(1, 3),
            base_processing_cost=random.randint(8, 12),
            base_value_increment=random.randint(4, 6),
            harvest_amount=random.randint(20, 30),
            reproduction_cost=random.randint(50, 70),
            energy_threshold_for_reproduction=random.randint(140,180),
            initial_traits=traits
        )
        env.add_entity(entity)
        # Ensure correct parameter names from previous steps (base_energy_per_cycle, etc.)
        # The Attentiophage __init__ was updated to use these base_ names.
        print(f"Added Entity {entity.entity_id} with traits: {entity.trait_manager}") # Print traits

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

            # Trait reporting (average traits from a sample of entities)
            sampled_traits = {}
            num_sampled_for_avg = 0
            sample_entities = list(env.entities.values())[:5] # Sample up to 5 entities

            if sample_entities:
                for sample_entity_obj in sample_entities: # Renamed inner loop var
                    for trait_name, score in sample_entity_obj.trait_manager.traits.items():
                        sampled_traits[trait_name] = sampled_traits.get(trait_name, 0) + score
                num_sampled_for_avg = len(sample_entities)

                for trait_name in sampled_traits:
                    sampled_traits[trait_name] /= num_sampled_for_avg

            # Main print statement for the step
            print(f"Entities: {current_entity_count}, Avg Energy: {average_energy:.2f}, Total Value (Cumulative): {total_value_generated_this_step}, Env Attention: {env.available_attention_units}")
            if sampled_traits: # Check if any traits were sampled and averaged
                avg_traits_str = ", ".join([f"{name}: {score:.2f}" for name, score in sampled_traits.items()])
                print(f"Avg Traits (sample of {num_sampled_for_avg}): {avg_traits_str}")
        else:
            print(f"No entities remaining. Env Attention: {env.available_attention_units}")
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

        final_avg_traits = {}
        for entity_obj_final in env.entities.values(): # Renamed loop var
            for trait_name, score in entity_obj_final.trait_manager.traits.items():
                final_avg_traits[trait_name] = final_avg_traits.get(trait_name, 0) + score
        # Check final_entity_count > 0 already done for this block
        for trait_name in final_avg_traits:
            final_avg_traits[trait_name] /= final_entity_count

        if final_avg_traits:
            final_avg_traits_str = ", ".join([f"{name}: {score:.2f}" for name, score in final_avg_traits.items()])
            print(f"Final average traits: {final_avg_traits_str}")

    print(f"Final available attention in environment: {env.available_attention_units}")

if __name__ == "__main__":
    run_simulation(num_steps=50, initial_entities=3) # Run for 50 steps with 3 initial entities
