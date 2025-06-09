import unittest
from unittest.mock import MagicMock, patch

from simulators.simulator01.entity import TraitManager, EnergyManager, CoreProcessor, AdaptationEngine, Attentiophage, ReproductionManager
from simulators.simulator01.environment import Environment

class TestTraitManager(unittest.TestCase):
    def test_initial_traits(self):
        tm = TraitManager({"Acquisitiveness": 0.7, "Cautiousness": 0.3})
        self.assertEqual(tm.get_trait("Acquisitiveness"), 0.7)
        self.assertEqual(tm.get_trait("Cautiousness"), 0.3)

    def test_get_default_trait(self):
        tm = TraitManager()
        self.assertEqual(tm.get_trait("NonExistentTrait"), 0.5) # Default value
        self.assertEqual(tm.get_trait("NonExistentTrait", 0.1), 0.1) # Custom default

    def test_set_trait(self):
        tm = TraitManager()
        tm.set_trait("TestTrait", 0.8)
        self.assertEqual(tm.get_trait("TestTrait"), 0.8)

    def test_set_trait_clamping(self):
        tm = TraitManager()
        tm.set_trait("HighTrait", 1.5)
        self.assertEqual(tm.get_trait("HighTrait"), 1.0) # Clamped
        tm.set_trait("LowTrait", -0.5)
        self.assertEqual(tm.get_trait("LowTrait"), 0.0) # Clamped

    def test_has_trait(self):
        tm = TraitManager({"Acquisitiveness": 0.7})
        self.assertTrue(tm.has_trait("Acquisitiveness"))
        self.assertFalse(tm.has_trait("NonExistentTrait"))

    def test_str_representation(self):
        traits = {"Acquisitiveness": 0.7, "Cautiousness": 0.3}
        tm = TraitManager(traits)
        self.assertEqual(str(tm), str(traits))

class TestEnergyManager(unittest.TestCase):
    def test_initial_energy(self):
        em = EnergyManager(initial_energy=100, max_energy=200, base_energy_per_cycle=1)
        self.assertEqual(em.current_energy, 100)
        self.assertEqual(em.base_energy_per_cycle, 1)


    def test_gain_energy(self):
        em = EnergyManager(initial_energy=50, max_energy=100)
        em.gain_energy(30)
        self.assertEqual(em.current_energy, 80)
        em.gain_energy(40)
        self.assertEqual(em.current_energy, 100)

    def test_lose_energy(self):
        em = EnergyManager(initial_energy=50)
        depleted = em.lose_energy(30)
        self.assertEqual(em.current_energy, 20)
        self.assertFalse(depleted)
        depleted = em.lose_energy(30)
        self.assertEqual(em.current_energy, -10)
        self.assertTrue(depleted)

    def test_metabolic_cost_no_traits(self):
        em = EnergyManager(initial_energy=20, base_energy_per_cycle=10)
        em.metabolic_cost(None)
        self.assertEqual(em.current_energy, 10)

    def test_metabolic_cost_with_destructiveness_trait(self):
        em = EnergyManager(initial_energy=100, base_energy_per_cycle=10)

        neutral_traits = TraitManager({"Destructiveness": 0.5}) # Expected multiplier 1.0
        em.current_energy = 100
        em.metabolic_cost(neutral_traits)
        self.assertEqual(em.current_energy, 90) # 100 - (10 * 1.0)

        high_dest_traits = TraitManager({"Destructiveness": 1.0}) # Expected multiplier 1.2
        em.current_energy = 100
        em.metabolic_cost(high_dest_traits) # 10 * 1.2 = 12
        self.assertEqual(em.current_energy, 88) # 100 - 12

        low_dest_traits = TraitManager({"Destructiveness": 0.0}) # Expected multiplier 0.8
        em.current_energy = 100
        em.metabolic_cost(low_dest_traits) # 10 * 0.8 = 8
        self.assertEqual(em.current_energy, 92) # 100 - 8


class TestCoreProcessor(unittest.TestCase):
    def test_init_values(self):
        cp = CoreProcessor(base_processing_cost=10, base_value_increment=5)
        self.assertEqual(cp.base_processing_cost, 10)
        self.assertEqual(cp.base_value_increment, 5)

    def test_process_information_no_traits(self):
        cp = CoreProcessor(base_processing_cost=10, base_value_increment=5)
        em = EnergyManager(initial_energy=100)
        processed = cp.process_information(em, None)
        self.assertTrue(processed)
        self.assertEqual(em.current_energy, 90) # 100 - 10
        self.assertEqual(cp.value_generated, 5) # 0 + 5

    def test_process_information_with_calculation_trait(self):
        cp = CoreProcessor(base_processing_cost=10, base_value_increment=5)
        em = EnergyManager(initial_energy=100)

        neutral_traits = TraitManager({"Calculation": 0.5}) # Cost mult 1.0, Value mult 1.0
        em.current_energy = 100; cp.value_generated = 0
        processed = cp.process_information(em, neutral_traits)
        self.assertTrue(processed)
        self.assertEqual(em.current_energy, 90) # Cost 10*1.0 = 10
        self.assertEqual(cp.value_generated, 5)  # Value 5*1.0 = 5

        high_calc_traits = TraitManager({"Calculation": 1.0}) # Cost mult 0.8, Value mult 1.2
        em.current_energy = 100; cp.value_generated = 0
        processed = cp.process_information(em, high_calc_traits)
        self.assertTrue(processed)
        self.assertEqual(em.current_energy, 92) # Cost 10*0.8 = 8
        self.assertEqual(cp.value_generated, 6)  # Value 5*1.2 = 6

        low_calc_traits = TraitManager({"Calculation": 0.0}) # Cost mult 1.2, Value mult 0.8
        em.current_energy = 100; cp.value_generated = 0
        processed = cp.process_information(em, low_calc_traits)
        self.assertTrue(processed) # Cost 10*1.2 = 12
        self.assertEqual(em.current_energy, 88)
        self.assertEqual(cp.value_generated, 4)  # Value 5*0.8 = 4

    def test_get_effective_processing_cost_no_traits(self):
        cp = CoreProcessor(base_processing_cost=10)
        self.assertEqual(cp.get_effective_processing_cost(None), 10)

    def test_get_effective_processing_cost_with_calculation_trait(self):
        cp = CoreProcessor(base_processing_cost=10)
        neutral_traits = TraitManager({"Calculation": 0.5}) # mult 1.0
        self.assertEqual(cp.get_effective_processing_cost(neutral_traits), 10)

        high_calc_traits = TraitManager({"Calculation": 1.0}) # mult 0.8
        self.assertEqual(cp.get_effective_processing_cost(high_calc_traits), 8)

        low_calc_traits = TraitManager({"Calculation": 0.0}) # mult 1.2
        self.assertEqual(cp.get_effective_processing_cost(low_calc_traits), 12)


class TestReproductionManager(unittest.TestCase):
    def setUp(self):
        self.mock_energy_manager = MagicMock(spec=EnergyManager)
        self.neutral_traits = TraitManager({
            "Cautiousness": 0.5, "RiskTaking": 0.5 # Cautious:1.0, Risk:1.0 -> Overall: 1.0
        })
        self.high_cautious_neutral_risk = TraitManager({
            "Cautiousness": 1.0, "RiskTaking": 0.5 # Cautious:1.2, Risk:1.0 -> Overall: 1.2
        })
        self.low_cautious_high_risk = TraitManager({
            "Cautiousness": 0.0, "RiskTaking": 1.0 # Cautious:0.8, Risk:0.9 -> Overall: 0.72
        })

    def test_should_reproduce_no_traits(self):
        rm = ReproductionManager(energy_threshold_for_reproduction=100)
        self.mock_energy_manager.current_energy = 100
        self.assertTrue(rm.should_reproduce(self.mock_energy_manager.current_energy, None))
        self.mock_energy_manager.current_energy = 99
        self.assertFalse(rm.should_reproduce(self.mock_energy_manager.current_energy, None))

    def test_should_reproduce_effects(self):
        rm = ReproductionManager(energy_threshold_for_reproduction=100)

        # Neutral: Effective threshold = 100 * 1.0 * 1.0 = 100
        self.mock_energy_manager.current_energy = 100
        self.assertTrue(rm.should_reproduce(self.mock_energy_manager.current_energy, self.neutral_traits))
        self.mock_energy_manager.current_energy = 99
        self.assertFalse(rm.should_reproduce(self.mock_energy_manager.current_energy, self.neutral_traits))

        # High Cautious, Neutral Risk: Effective threshold = 100 * 1.2 (cautious) * 1.0 (risk) = 120
        self.mock_energy_manager.current_energy = 120
        self.assertTrue(rm.should_reproduce(self.mock_energy_manager.current_energy, self.high_cautious_neutral_risk))
        self.mock_energy_manager.current_energy = 119
        self.assertFalse(rm.should_reproduce(self.mock_energy_manager.current_energy, self.high_cautious_neutral_risk))

        # Low Cautious, High Risk: Effective threshold = 100 * 0.8 (cautious) * 0.9 (risk) = 72
        self.mock_energy_manager.current_energy = 72
        self.assertTrue(rm.should_reproduce(self.mock_energy_manager.current_energy, self.low_cautious_high_risk))
        self.mock_energy_manager.current_energy = 71
        self.assertFalse(rm.should_reproduce(self.mock_energy_manager.current_energy, self.low_cautious_high_risk))

    def test_reproduce_call_with_traits(self):
        rm = ReproductionManager(reproduction_cost=50, energy_threshold_for_reproduction=100)
        self.mock_energy_manager.current_energy = 100
        self.mock_energy_manager.lose_energy = MagicMock()

        # We mock should_reproduce to ensure it's called correctly, and to isolate reproduce's own logic
        with patch.object(rm, 'should_reproduce', return_value=True) as mock_should_reproduce:
            reproduced = rm.reproduce(self.mock_energy_manager, "test_id", self.neutral_traits)
            self.assertTrue(reproduced)
            mock_should_reproduce.assert_called_once_with(self.mock_energy_manager.current_energy, self.neutral_traits)
            self.mock_energy_manager.lose_energy.assert_called_once_with(50)


class TestAttentiophage(unittest.TestCase):
    def setUp(self):
        self.mock_environment = MagicMock(spec=Environment)
        # Default behavior for provide_attention, can be overridden per test
        self.mock_environment.provide_attention = MagicMock(side_effect=lambda requested: requested)

        self.base_params = {
            "entity_id": "E1", "initial_energy": 100, "max_energy": 200,
            "base_energy_per_cycle": 5, "base_processing_cost": 10,
            "base_value_increment": 5, "harvest_amount": 20, # This is base harvest amount
            "reproduction_cost": 50, "energy_threshold_for_reproduction": 180,
        }
        self.neutral_traits_dict = {
            "Acquisitiveness": 0.5, "Cautiousness": 0.5, "RiskTaking": 0.5,
            "Calculation": 0.5, "Destructiveness": 0.5
        }

    def test_attentiophage_creation_with_traits(self):
        params = self.base_params.copy()
        params["initial_traits"] = self.neutral_traits_dict.copy()
        entity = Attentiophage(**params)
        self.assertTrue(entity.is_alive)
        self.assertEqual(entity.entity_id, "E1")
        self.assertEqual(entity.energy_manager.current_energy, 100)
        self.assertIsNotNone(entity.trait_manager)
        self.assertEqual(entity.trait_manager.get_trait("Acquisitiveness"), 0.5)

    def test_perform_cycle_acquisitiveness_effect(self):
        params = self.base_params.copy()
        traits = self.neutral_traits_dict.copy()
        traits["Acquisitiveness"] = 1.0 # Multiplier 1.5 -> effective harvest 20 * 1.5 = 30
        params["initial_traits"] = traits

        entity = Attentiophage(**params) # base_harvest_amount is 20

        # initial_energy = 100
        # harvest = 30 (because Acq=1.0 -> multiplier 1.5)
        # processing_cost = 10 (base_processing_cost=10, Calculation=0.5 -> mult 1.0)
        # metabolic_cost = 5 (base_energy_per_cycle=5, Destructiveness=0.5 -> mult 1.0)
        # Expected energy: 100 + 30 - 10 - 5 = 115
        # Expected value: 5 (base_value_increment=5, Calculation=0.5 -> mult 1.0)

        entity.perform_cycle_actions(self.mock_environment)

        # Check that provide_attention was called with the effective amount
        self.mock_environment.provide_attention.assert_called_with(30)
        self.assertEqual(entity.energy_manager.current_energy, 115)
        self.assertEqual(entity.core_processor.value_generated, 5)

# Minimal TestEnvironment to ensure file is runnable, assuming it exists from previous steps
# More tests for Environment would be in a complete suite.
class TestEnvironment(unittest.TestCase):
    def test_env_creation(self):
        env = Environment()
        self.assertIsNotNone(env)
        self.assertEqual(env.current_step, 0)


if __name__ == '__main__':
    unittest.main()
