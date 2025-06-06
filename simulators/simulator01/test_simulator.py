import unittest
from unittest.mock import MagicMock, patch

# Assuming the simulator01 directory is in a package 'simulators'
# Adjust the import path if your structure is different or run from a specific CWD.
from simulators.simulator01.entity import EnergyManager, CoreProcessor, AdaptationEngine, Attentiophage, ReproductionManager
from simulators.simulator01.environment import Environment

class TestEnergyManager(unittest.TestCase):
    def test_initial_energy(self):
        em = EnergyManager(initial_energy=100, max_energy=200, energy_per_cycle=1)
        self.assertEqual(em.current_energy, 100)

    def test_gain_energy(self):
        em = EnergyManager(initial_energy=50, max_energy=100)
        em.gain_energy(30)
        self.assertEqual(em.current_energy, 80)
        em.gain_energy(40) # Try to exceed max
        self.assertEqual(em.current_energy, 100)

    def test_lose_energy(self):
        em = EnergyManager(initial_energy=50)
        depleted = em.lose_energy(30)
        self.assertEqual(em.current_energy, 20)
        self.assertFalse(depleted)
        depleted = em.lose_energy(30) # Exceeds current energy
        self.assertEqual(em.current_energy, -10) # Or 0 if capped, current implementation goes negative
        self.assertTrue(depleted) # Depleted because it went to/below 0

    def test_metabolic_cost(self):
        em = EnergyManager(initial_energy=10, energy_per_cycle=3)
        depleted = em.metabolic_cost()
        self.assertEqual(em.current_energy, 7)
        self.assertFalse(depleted)
        em.metabolic_cost() # 4
        em.metabolic_cost() # 1
        depleted = em.metabolic_cost() # -2
        self.assertEqual(em.current_energy, -2)
        self.assertTrue(depleted)

class TestCoreProcessor(unittest.TestCase):
    def test_process_information_sufficient_energy(self):
        em = EnergyManager(initial_energy=100) # Removed processing_cost from EM init
        cp = CoreProcessor(processing_cost=10)
        processed = cp.process_information(em)
        self.assertTrue(processed)
        self.assertEqual(em.current_energy, 90) # 100 - 10
        self.assertEqual(cp.value_generated, 5)

    def test_process_information_insufficient_energy(self):
        em = EnergyManager(initial_energy=5) # Removed processing_cost from EM init
        cp = CoreProcessor(processing_cost=10)
        processed = cp.process_information(em)
        self.assertFalse(processed)
        self.assertEqual(em.current_energy, 5) # Energy unchanged
        self.assertEqual(cp.value_generated, 0) # Value unchanged

class TestReproductionManager(unittest.TestCase):
    def setUp(self):
        self.mock_energy_manager = MagicMock(spec=EnergyManager)

    def test_should_reproduce_true(self):
        rm = ReproductionManager(reproduction_cost=50, energy_threshold_for_reproduction=150)
        self.mock_energy_manager.current_energy = 160
        self.assertTrue(rm.should_reproduce(self.mock_energy_manager.current_energy))

    def test_should_reproduce_false_below_threshold(self):
        rm = ReproductionManager(reproduction_cost=50, energy_threshold_for_reproduction=150)
        self.mock_energy_manager.current_energy = 140
        self.assertFalse(rm.should_reproduce(self.mock_energy_manager.current_energy))

    def test_reproduce_successful(self):
        rm = ReproductionManager(reproduction_cost=50, energy_threshold_for_reproduction=150)
        self.mock_energy_manager.current_energy = 160
        # Mock lose_energy to check it's called
        self.mock_energy_manager.lose_energy = MagicMock()

        reproduced = rm.reproduce(self.mock_energy_manager, "test_id")

        self.assertTrue(reproduced)
        self.mock_energy_manager.lose_energy.assert_called_once_with(50)

    def test_reproduce_fail_insufficient_energy_for_cost(self):
        # Energy is above threshold, but not enough to cover the cost AFTER deciding to reproduce
        # This scenario is more about the check within reproduce() itself
        # rm = ReproductionManager(reproduction_cost=100, energy_threshold_for_reproduction=150)
        self.mock_energy_manager.current_energy = 160 # Above threshold, but 160 < 100 is false for cost

        # This test highlights that `should_reproduce` uses current_energy >= threshold,
        # and `reproduce` also checks current_energy >= cost.
        # If current_energy is 160, threshold 150, cost 170, should_reproduce is true, reproduce is false.
        rm_high_cost = ReproductionManager(reproduction_cost=170, energy_threshold_for_reproduction=150)
        reproduced = rm_high_cost.reproduce(self.mock_energy_manager, "test_id")
        self.assertFalse(reproduced)
        self.mock_energy_manager.lose_energy.assert_not_called()


class TestAttentiophage(unittest.TestCase):
    def setUp(self):
        self.mock_environment = MagicMock(spec=Environment)
        self.mock_environment.provide_attention.return_value = 20 # Simulate getting 20 energy

        # Default config for Attentiophage
        self.entity_config = {
            "entity_id": "E1", # Will be overridden if added to env, but good for direct instantiation
            "initial_energy": 100,
            "max_energy": 200,
            "energy_per_cycle": 5,
            "processing_cost": 10,
            "harvest_amount": 20,
            "reproduction_cost": 50,
            "energy_threshold_for_reproduction": 180 # High threshold to prevent reproduction by default
        }

    def test_attentiophage_creation(self):
        entity = Attentiophage(**self.entity_config)
        self.assertTrue(entity.is_alive)
        self.assertEqual(entity.entity_id, "E1")
        self.assertEqual(entity.energy_manager.current_energy, 100)

    def test_perform_cycle_actions_normal_cycle(self):
        entity = Attentiophage(**self.entity_config)
        initial_energy = entity.energy_manager.current_energy # 100

        entity.perform_cycle_actions(self.mock_environment) # harvest +20, process -10, metabolic -5

        self.mock_environment.provide_attention.assert_called_once_with(entity.harvest_amount)
        self.assertEqual(entity.energy_manager.current_energy, initial_energy + 20 - 10 - 5) # 100 + 20 - 10 - 5 = 105
        self.assertTrue(entity.is_alive)
        self.assertEqual(entity.core_processor.value_generated, 5)

    def test_attentiophage_death_from_metabolic_cost(self):
        config = self.entity_config.copy()
        config["initial_energy"] = 10 # Very low energy
        config["energy_per_cycle"] = 15 # High metabolic cost
        config["processing_cost"] = 0 # No processing to isolate metabolic death
        self.mock_environment.provide_attention.return_value = 0 # No energy from environment

        entity = Attentiophage(**config)

        entity.perform_cycle_actions(self.mock_environment) # harvest +0, process -0, metabolic -15
                                                        # 10 - 15 = -5

        self.assertFalse(entity.is_alive)
        self.assertEqual(entity.energy_manager.current_energy, -5)

    @patch('simulators.simulator01.entity.ReproductionManager.reproduce')
    def test_attentiophage_reproduction_triggers_env_add_offspring(self, mock_reproduction_manager_reproduce):
        # ReproductionManager.reproduce is mocked to always return True (successful energy deduction for reproduction)
        mock_reproduction_manager_reproduce.return_value = True

        config = self.entity_config.copy()
        config["initial_energy"] = 190
        config["energy_threshold_for_reproduction"] = 180 # Entity energy > threshold
        config["reproduction_cost"] = 50 # This cost is handled by the (mocked) ReproductionManager

        entity = Attentiophage(**config)
        # Ensure energy is high enough to trigger 'should_reproduce'
        entity.energy_manager.current_energy = 190

        self.mock_environment.add_offspring = MagicMock() # Mock env's method

        entity.perform_cycle_actions(self.mock_environment)

        # Check that ReproductionManager.reproduce was called
        # The instance of ReproductionManager is entity.reproduction_manager
        # So we need to patch that specific instance's method or the class method if it's always the same logic.
        # The current patch on the class method is fine if all instances behave the same way for the mock.
        mock_reproduction_manager_reproduce.assert_called_once_with(entity.energy_manager, str(entity.entity_id))

        # Check that environment's add_offspring was called
        self.mock_environment.add_offspring.assert_called_once()

        # Energy check:
        # Start: 190
        # Harvest: +20 (from mock_environment.provide_attention)
        # Process: -10 (entity.core_processor.processing_cost)
        # Reproduction: Cost is handled by the mocked ReproductionManager.reproduce.
        #               The actual energy deduction via entity.energy_manager.lose_energy(reproduction_cost)
        #               would happen inside the *real* ReproductionManager.reproduce.
        #               Since we mocked it, this deduction doesn't happen on the actual energy_manager here
        #               UNLESS the mock itself calls it. The default MagicMock doesn't.
        # Metabolic: -5 (entity.energy_manager.energy_per_cycle)
        # Expected: 190 + 20 - 10 - 5 = 195
        # This highlights that the mocked 'reproduce' returning True bypasses its internal logic, including energy deduction.
        # For a more integrated test of energy, we'd need the real reproduce or a mock that also calls lose_energy.
        # This test correctly verifies the interaction: if reproduce() says yes, add_offspring() is called.
        self.assertEqual(entity.energy_manager.current_energy, 190 + 20 - 10 - 5)


class TestEnvironment(unittest.TestCase):
    def test_add_entity(self):
        env = Environment()
        # Pass a dummy entity_id, it will be overwritten by env.add_entity
        entity = Attentiophage(entity_id="temp_id")
        env.add_entity(entity)
        self.assertEqual(len(env.entities), 1)
        self.assertEqual(entity.entity_id, 0) # First entity gets ID 0
        self.assertIn(0, env.entities)

    def test_remove_entity(self):
        env = Environment()
        entity = Attentiophage(entity_id="temp_id")
        env.add_entity(entity)
        entity_id_to_remove = entity.entity_id # This will be 0
        env.remove_entity(entity_id_to_remove)
        self.assertEqual(len(env.entities), 0)

    def test_provide_attention(self):
        env = Environment(initial_attention_units=100)
        provided = env.provide_attention(50)
        self.assertEqual(provided, 50)
        self.assertEqual(env.available_attention_units, 50)
        provided = env.provide_attention(60) # Request more than available
        self.assertEqual(provided, 50) # Should give remaining
        self.assertEqual(env.available_attention_units, 0)
        provided = env.provide_attention(10) # Request when empty
        self.assertEqual(provided, 0)

    def test_regenerate_attention(self):
        env = Environment(initial_attention_units=100, attention_units_per_step=20)
        env.regenerate_attention()
        self.assertEqual(env.available_attention_units, 120)

    def test_simulation_step_removes_dead_entities(self):
        env = Environment()
        # Entity configured to die in one step:
        # Initial energy 1, harvest 0 (mocked), process 0, metabolic cost 1
        dying_entity = Attentiophage(entity_id="temp", initial_energy=1, energy_per_cycle=1, processing_cost=0, harvest_amount=0)
        env.add_entity(dying_entity) # ID becomes 0

        # Mock provide_attention for this entity during the step
        # The environment instance `env` is what entity will call.
        # So, we can patch `env.provide_attention`
        with patch.object(env, 'provide_attention', return_value=0) as mock_provide_attention:
            env.simulation_step()
            mock_provide_attention.assert_called_with(dying_entity.harvest_amount)

        self.assertEqual(len(env.entities), 0, "Dead entity should be removed after simulation step")


    def test_add_offspring_within_and_exceeding_capacity(self):
        env = Environment(max_entities=1) # Max 1 entity
        # Parent entity config
        parent_config = {"entity_id": "parent", "initial_energy": 100}
        parent_entity = Attentiophage(**parent_config)
        env.add_entity(parent_entity) # Environment has 1 entity (parent, ID 0)

        self.assertEqual(len(env.entities), 1)

        offspring_config = {"initial_energy": 50}
        # Attempt to add offspring - should fail as capacity is 1
        env.add_offspring(offspring_config)
        self.assertEqual(len(env.entities), 1, "Offspring should not be added if env is at capacity")

        env.max_entities = 2 # Increase capacity to 2
        # Attempt to add offspring again - should succeed now
        env.add_offspring(offspring_config)
        self.assertEqual(len(env.entities), 2, "Offspring should be added when capacity allows")
        # The new entity should have ID 1 (parent was 0)
        self.assertIn(1, env.entities)
        self.assertEqual(env.entities[1].energy_manager.current_energy, 50)


if __name__ == '__main__':
    unittest.main()
