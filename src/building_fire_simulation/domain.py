"""Domain objects and parameter catalogues for the building-fire model."""

from typing import List, Tuple, Optional, Dict, Set
from collections import defaultdict
from abc import ABC, abstractmethod
import random
import numpy as np

from building_fire_simulation.probability_distributions import (
    normal_sampler
)

class Coordinate:
    """Represents a point in 3D Euclidean space."""
    def __init__(self, x: int, y: int, z: int):
        self.x = x
        self.y = y
        self.z = z

    def as_tuple(self) -> Tuple[int, int, int]:
        return (self.x, self.y, self.z)

    def __repr__(self):
        return f"Coordinate({self.x}, {self.y}, {self.z})"

    def __eq__(self, other):
        if isinstance(other, Coordinate):
            return (self.x, self.y, self.z) == (other.x, other.y, other.z)
        return False

    def __hash__(self):
        return hash((self.x, self.y, self.z))

# Default values for material variables.
DEFAULT_BURN_RESISTANCE = 0.5
DEFAULT_QMAX = 0.0
DEFAULT_LAMBDA_DECAY = 0.01
DEFAULT_T_IGNITION = 30.0

class Material:
    """
    Represents the fire-relevant properties of a building surface material.
    """
    def __init__(self, name: str, burn_resistance: float, q_max: float, lambda_decay: float,
                 t_ignition: float, ignition_temp: float, t_peak: float, energy_density: float = 0.0):
        self.name = name
        self.burn_resistance = burn_resistance
        self.q_max = q_max
        self.lambda_decay = lambda_decay
        self.t_ignition = t_ignition
        self.ignition_temp = ignition_temp
        self.energy_density = energy_density  # MJ/kg
        self.t_peak = t_peak

    def __repr__(self):
        return (f"<Material {self.name}, resistance={self.burn_resistance}, "
                f"Qmax={self.q_max}, lambda={self.lambda_decay}, "
                f"T_ign={self.t_ignition}, ignition_temp={self.ignition_temp}, "
                f"energy_density={self.energy_density}, t_peak={self.t_peak}>")

STRUCTURAL_MATERIALS = {
    "concrete": Material("concrete", burn_resistance=0.95, q_max=0.0, lambda_decay=0.01, t_ignition=999, ignition_temp=999, t_peak=999),
    "brick": Material("brick", burn_resistance=0.93, q_max=0.0, lambda_decay=0.01, t_ignition=999, ignition_temp=999, t_peak=999),
    "metal": Material("metal", burn_resistance=0.90, q_max=0.0, lambda_decay=0.01, t_ignition=999, ignition_temp=999, t_peak=999),
    "steel": Material("steel", burn_resistance=0.90, q_max=0.0, lambda_decay=0.01, t_ignition=999, ignition_temp=999, t_peak=999),
    "supersteel": Material("supersteel", burn_resistance=0.98, q_max=0.0, lambda_decay=0.005, t_ignition=999, ignition_temp=999, t_peak=999),
    "wood (structural)": Material("wood (structural)", burn_resistance=0.4, q_max=250, lambda_decay=0.015, t_ignition=20, ignition_temp=300, t_peak=150),
}


COVER_MATERIALS = {
    "insulating fiberboard": Material("insulating fiberboard", burn_resistance=0.25, q_max=280, lambda_decay=0.015, t_ignition=10, ignition_temp=270, t_peak=20, energy_density=15.0),
    "medium density fiberboard": Material("medium density fiberboard", burn_resistance=0.35, q_max=270, lambda_decay=0.012, t_ignition=12, ignition_temp=285, t_peak=30, energy_density=16.5),
    "particle board": Material("particle board", burn_resistance=0.33, q_max=265, lambda_decay=0.011, t_ignition=14, ignition_temp=290, t_peak=27, energy_density=16.0),
    "gypsum plasterboard": Material("gypsum plasterboard", burn_resistance=0.85, q_max=50, lambda_decay=0.020, t_ignition=90, ignition_temp=999, t_peak=40, energy_density=2.0),
    "PVC on gypsum": Material("PVC on gypsum", burn_resistance=0.45, q_max=110, lambda_decay=0.025, t_ignition=30, ignition_temp=340, t_peak=15, energy_density=12.0),
    "paper on gypsum": Material("paper on gypsum", burn_resistance=0.40, q_max=120, lambda_decay=0.020, t_ignition=25, ignition_temp=230, t_peak=12, energy_density=10.0),
    "textile on gypsum": Material("textile on gypsum", burn_resistance=0.38, q_max=170, lambda_decay=0.019, t_ignition=20, ignition_temp=310, t_peak=17, energy_density=13.0),
    "textile on mineral wool": Material("textile on mineral wool", burn_resistance=0.36, q_max=200, lambda_decay=0.017, t_ignition=18, ignition_temp=320, t_peak=18, energy_density=14.0),
    "melamine-faced particle board": Material("melamine-faced particle board", burn_resistance=0.30, q_max=220, lambda_decay=0.018, t_ignition=22, ignition_temp=300, t_peak=20, energy_density=17.0),
    "expanded polystyrene": Material("expanded polystyrene", burn_resistance=0.15, q_max=500, lambda_decay=0.040, t_ignition=4, ignition_temp=370, t_peak=7, energy_density=35.0),
    "rigid polyurethane foam": Material("rigid polyurethane foam", burn_resistance=0.18, q_max=450, lambda_decay=0.035, t_ignition=6, ignition_temp=360, t_peak=8, energy_density=32.0),
    "wood panel, spruce": Material("wood panel, spruce", burn_resistance=0.42, q_max=290, lambda_decay=0.013, t_ignition=13, ignition_temp=300, t_peak=30, energy_density=18.5),
    "paper on particle board": Material("paper on particle board", burn_resistance=0.32, q_max=260, lambda_decay=0.014, t_ignition=16, ignition_temp=260, t_peak=22, energy_density=15.0),
}


MATERIALS_FOR_ITEMS = {
    "wood": Material(name="wood", burn_resistance=0.4, q_max=250.0, lambda_decay=0.015, t_ignition=20.0, ignition_temp=300.0, energy_density=18.0, t_peak=30),
    "wood_oak": Material(name="wood_oak", burn_resistance=0.5, q_max=270.0, lambda_decay=0.002, t_ignition=23.0, ignition_temp=320.0, energy_density=20.0, t_peak=60),
    "laminated_wood": Material(name="laminated_wood", burn_resistance=0.55, q_max=180.0, lambda_decay=0.012, t_ignition=150.0, ignition_temp=330.0, energy_density=15.0, t_peak=40),
    "plastic": Material(name="plastic", burn_resistance=0.2, q_max=400.0, lambda_decay=0.020, t_ignition=8.0, ignition_temp=350.0, energy_density=35.0, t_peak=15),
    "paper": Material(name="paper", burn_resistance=0.1, q_max=300.0, lambda_decay=0.030, t_ignition=5.0, ignition_temp=270.0, energy_density=17.0, t_peak=5),
    "fabric": Material(name="fabric", burn_resistance=0.25, q_max=180.0, lambda_decay=0.020, t_ignition=12.0, ignition_temp=290.0, energy_density=18.0, t_peak=12),
    "leather_and_foam": Material(name="leather_and_foam", burn_resistance=0.20, q_max=450.0, lambda_decay=0.020, t_ignition=7.0, ignition_temp=340.0, energy_density=39.0, t_peak=10),
    "foam": Material(name="foam", burn_resistance=0.15, q_max=450.0, lambda_decay=0.020, t_ignition=6.0, ignition_temp=340.0, energy_density=38.0, t_peak=8),
    "rubber": Material(name="rubber", burn_resistance=0.3, q_max=320.0, lambda_decay=0.028, t_ignition=15.0, ignition_temp=310.0, energy_density=30.0, t_peak=20),
    "carpet_material": Material(name="carpet_material", burn_resistance=0.0, q_max=350.0, lambda_decay=0.020, t_ignition=8.0, ignition_temp=260.0, energy_density=18.0, t_peak=17),
}

MATERIALS_FOR_DOORS = {
    "thin_plywood": Material(name="thin_plywood", burn_resistance=0.2, q_max=300.0, lambda_decay=0.020, t_ignition=10.0, ignition_temp=250.0, energy_density=14.0, t_peak=17),
    "solid_wood": Material(name="solid_wood", burn_resistance=0.4, q_max=250.0, lambda_decay=0.015, t_ignition=20.0, ignition_temp=300.0, energy_density=16.0, t_peak=33),
    "laminated_wood": Material(name="laminated_wood", burn_resistance=0.55, q_max=200.0, lambda_decay=0.012, t_ignition=30.0, ignition_temp=330.0, energy_density=15.0, t_peak=40),
    "wood_oak": Material(name="wood_oak", burn_resistance=0.5, q_max=270.0, lambda_decay=0.002, t_ignition=23.0, ignition_temp=320.0, energy_density=20.0, t_peak=60),
    "fire_door_mdf": Material(name="fire_door_mdf", burn_resistance=0.75, q_max=120.0, lambda_decay=0.010, t_ignition=45.0, ignition_temp=360.0, energy_density=12.0, t_peak=30),
    "steel_door": Material(name="steel_door", burn_resistance=0.95, q_max=20.0, lambda_decay=0.005, t_ignition=90.0, ignition_temp=1000.0, energy_density=1.0, t_peak=50),
}

MATERIALS_FOR_WINDOWS = {
    "plastic_frame": Material(name="plastic_frame", burn_resistance=0.1, q_max=320.0, lambda_decay=0.020, t_ignition=8.0, ignition_temp=220.0, energy_density=18.0, t_peak=12),
    "softwood_frame": Material(name="softwood_frame", burn_resistance=0.3, q_max=280.0, lambda_decay=0.018, t_ignition=15.0, ignition_temp=270.0, energy_density=16.0, t_peak=25),
    "hardwood_frame": Material(name="hardwood_frame", burn_resistance=0.45, q_max=230.0, lambda_decay=0.013, t_ignition=25.0, ignition_temp=310.0, energy_density=15.0, t_peak=40),
    "aluminum_frame": Material(name="aluminum_frame", burn_resistance=0.8, q_max=40.0, lambda_decay=0.007, t_ignition=60.0, ignition_temp=660.0, energy_density=2.0, t_peak=33),
    "reinforced_glass": Material(name="reinforced_glass", burn_resistance=0.97, q_max=10.0, lambda_decay=0.003, t_ignition=100.0, ignition_temp=1200.0, energy_density=0.5, t_peak=50),
}

MATERIALS_FOR_STAIRS = {
    "pine_wood": Material(name="pine_wood", burn_resistance=0.25, q_max=300.0, lambda_decay=0.02, t_ignition=12.0, ignition_temp=260.0, energy_density=17.0, t_peak=23),
    "oak_wood": Material(name="oak_wood", burn_resistance=0.4, q_max=240.0, lambda_decay=0.002, t_ignition=22.0, ignition_temp=300.0, energy_density=15.5, t_peak=53),
    "steel_frame": Material(name="steel_frame", burn_resistance=0.95, q_max=20.0, lambda_decay=0.005, t_ignition=80.0, ignition_temp=1100.0, energy_density=1.5, t_peak=50),
}

MATERIALS_FOR_MISCELLANIOUS_SETS = {
    "cool_and_porous": Material(name="cool_and_porous", burn_resistance=0.4, q_max=100.0, lambda_decay=0.015, t_ignition=15.0, ignition_temp=300.0, energy_density=10.0, t_peak=20),
    "cool_and_medium_dense": Material(name="cool_and_medium_dense", burn_resistance=0.4, q_max=100.0, lambda_decay=0.015, t_ignition=17.0, ignition_temp=300.0, energy_density=15.0, t_peak=27),
    "cool_and_dense": Material(name="cool_and_dense", burn_resistance=0.4, q_max=100.0, lambda_decay=0.015, t_ignition=20.0, ignition_temp=300.0, energy_density=20.0, t_peak=33),
    "medium_hot_and_porous": Material(name="medium_hot_and_porous", burn_resistance=0.4, q_max=200.0, lambda_decay=0.015, t_ignition=15.0, ignition_temp=300.0, energy_density=10.0, t_peak=20),
    "medium_hot_and_medium_dense": Material(name="medium_hot_and_medium_dense", burn_resistance=0.4, q_max=200.0, lambda_decay=0.015, t_ignition=17.0, ignition_temp=300.0, energy_density=15.0, t_peak=27),
    "medium_hot_and_dense": Material(name="medium_hot_and_dense", burn_resistance=0.4, q_max=200.0, lambda_decay=0.015, t_ignition=20.0, ignition_temp=300.0, energy_density=20.0, t_peak=33),
    "hot_and_porous": Material(name="hot_and_porous", burn_resistance=0.4, q_max=350.0, lambda_decay=0.015, t_ignition=15.0, ignition_temp=300.0, energy_density=10.0, t_peak=20),
    "hot_and_medium_dense": Material(name="hot_and_medium_dense", burn_resistance=0.4, q_max=350.0, lambda_decay=0.015, t_ignition=17.0, ignition_temp=300.0, energy_density=15.0, t_peak=27),
    "hot_and_dense": Material(name="hot_and_dense", burn_resistance=0.4, q_max=350.0, lambda_decay=0.015, t_ignition=20.0, ignition_temp=300.0, energy_density=20.0, t_peak=33)
}

# ITEM_MAX_HEAT = 1000.0 # Maximum heat release by an object.
BURN_FRACTION = 0.04 # Percent of item mass burning at a given time.

import math

class FireBehavior:
    """
    HRR: t^r growth -> optional plateau -> exponential decay.
    Ignition: requires air_temp >= ignition_temp continuously for t_ignition seconds.
    Energy bookkeeping in kJ (HRR kW * s).
    """
    def __init__(self, material: Material, mass_kg: float):
        self.material = material
        self.mass_kg = max(0.0, mass_kg)

        # Ignition state
        self.time_above_ignition_temp: float = 0.0
        self.is_ignited: bool = False
        self._ignition_time: float | None = None
        self._last_ignition_check_time: float | None = None

        # Energy bookkeeping (kJ). Assume energy_density is MJ/kg.
        self.total_energy = self.mass_kg * self.material.energy_density * 1000.0
        self.released_energy = 0.0
        self.latest_heat_output = 0.0

        # HRR curve internals
        self._curve_ready = False
        self._r = 2.0
        self._beta = getattr(self.material, "lambda_decay", 1.0) or 1.0
        self._q_peak = None
        self._t_peak_eff = None
        self._t_hold = None
        self._tau = None
        self._t0_ignition = None
        self._last_eval_time = None

    # --- convenience helpers ---
    def is_active(self, epsilon_kJ: float = 1e-3) -> bool:
        """
        Active := currently burning OR emitted measurable heat this tick.
        Residual unburned fuel alone does not count as active.
        """
        return bool(self.is_ignited or (getattr(self, "latest_heat_output", 0.0) > epsilon_kJ))


    def force_ignite(self, now: float) -> None:
        """Public helper for start_fire: start HRR at 'now' without taking energy yet."""
        self.is_ignited = True
        self.time_above_ignition_temp = self.material.t_ignition or 0.0
        self._ignition_time = now
        self._curve_ready = False
        self._last_eval_time = now
        self._last_ignition_check_time = now

    # --- call this every tick BEFORE heat_release ---
    def update_ignition(self, air_temp: float, now: float) -> bool:
        """
        Returns True the instant the object ignites.
        Requires continuous exposure: air_temp >= ignition_temp for t_ignition seconds.
        """
        # Always advance the internal clock to avoid huge dt jumps on re-check.
        dt = max(0.0, now - (self._last_ignition_check_time or now))
        self._last_ignition_check_time = now

        # Out of fuel? Never (re)ignite.
        if self.released_energy >= self.total_energy or self.mass_kg <= 0.0:
            return False

        # Already burning: we don't accumulate exposure while ignited.
        if self.is_ignited:
            return False

        # Update continuous exposure timer
        if air_temp >= self.material.ignition_temp:
            self.time_above_ignition_temp += dt
        else:
            self.time_above_ignition_temp = 0.0

        # Check ignition criterion
        if self.time_above_ignition_temp >= (self.material.t_ignition or 0.0):
            self.is_ignited = True
            self._ignition_time = now
            self._curve_ready = False
            self._last_eval_time = now
            return True

        return False

    # --- internals for HRR setup ---
    def _precompute_curve(self):
        t_peak = self.material.t_peak or 1.0
        self._t_peak_eff = max(1e-6, t_peak * max(self.mass_kg, 1e-6))
        q_target = max(0.0, self.material.q_max)
        E_tot = max(0.0, self.total_energy)

        # Feasibility: cap peak if not enough energy to reach q_target by t_peak
        E_grow_min = q_target * self._t_peak_eff / (self._r + 1.0)
        if E_tot < E_grow_min:
            q_peak = (E_tot * (self._r + 1.0)) / max(self._t_peak_eff, 1e-6)
        else:
            q_peak = q_target

        tau = self._beta * self._t_peak_eff
        t_hold = (E_tot / max(q_peak, 1e-9)) - (self._t_peak_eff / (self._r + 1.0)) - tau
        if t_hold < 0.0:
            t_hold = 0.0
            tau = max((E_tot / max(q_peak, 1e-9)) - (self._t_peak_eff / (self._r + 1.0)), 1e-6)

        self._q_peak = q_peak
        self._tau = tau
        self._t_hold = t_hold
        self._curve_ready = True

    def _hrr_at_elapsed(self, t_elapsed: float) -> float:
        if t_elapsed <= 0.0:
            return 0.0
        t_p = self._t_peak_eff
        q = self._q_peak
        if t_elapsed < t_p:
            return q * (t_elapsed / t_p) ** self._r
        elif t_elapsed < t_p + self._t_hold:
            return q
        else:
            return q * math.exp(-(t_elapsed - t_p - self._t_hold) / self._tau)

    def heat_release(self, burn_time: float, verbose=False) -> float:
        """
        Returns kJ released during [last_call, burn_time].
        Assumes update_ignition(...) was called earlier this tick.
        """
        # Not ignited: no heat, but keep time in sync for next Δt
        if not self.is_ignited:
            self._last_eval_time = burn_time
            self.latest_heat_output = 0.0
            return 0.0

        # Out of fuel
        if self.released_energy >= self.total_energy or self.mass_kg <= 0.0:
            self.latest_heat_output = 0.0
            self.is_ignited = False
            self.time_above_ignition_temp = 0.0
            return 0.0

        # Initialize HRR curve starting exactly at ignition time
        if not self._curve_ready:
            self._t0_ignition = self._ignition_time if self._ignition_time is not None else burn_time
            self._precompute_curve()
            self._last_eval_time = burn_time
            if verbose:
                print(f"[init] q_peak={self._q_peak:.2f} kW, t_peak_eff={self._t_peak_eff:.2f}s, "
                      f"t_hold={self._t_hold:.2f}s, tau={self._tau:.2f}s, E_tot={self.total_energy:.1f} kJ")
            return 0.0

        # Integrate over this step
        dt = max(0.0, burn_time - (self._last_eval_time or burn_time))
        self._last_eval_time = burn_time
        if dt <= 0.0:
            self.latest_heat_output = 0.0
            return 0.0

        t_elapsed = burn_time - self._t0_ignition
        q_kW = self._hrr_at_elapsed(t_elapsed)
        dE = q_kW * dt

        # Clip to remaining energy
        remaining = self.total_energy - self.released_energy
        if dE > remaining:
            dE = remaining

        self.released_energy += dE
        self.latest_heat_output = dE

        # Auto-extinguish: on full burnout OR vanishing tail after the peak
        if self.released_energy >= self.total_energy or (q_kW < 0.2 and t_elapsed > self._t_peak_eff):
            self.is_ignited = False
            self.time_above_ignition_temp = 0.0  # require fresh exposure for re-ignition

        if verbose:
            print(f"[heat_release] t={t_elapsed:.1f}s, dt={dt:.2f}s, q={q_kW:.2f} kW, dE={dE:.2f} kJ, "
                  f"E={self.released_energy:.1f}/{self.total_energy:.1f} kJ")
        return dE

    def __repr__(self):
        return (f"<FireBehavior material={self.material.name}, mass={self.mass_kg}kg, "
                f"released={self.released_energy:.1f}/{self.total_energy:.1f} kJ, "
                f"latest_heat_output={self.latest_heat_output:.3f} kJ, is_ignited={self.is_ignited}>")

from abc import ABC, abstractmethod
from typing import Optional
import math

class Item(ABC):
    """Base class for any object attached to a cube or component in the building."""
    def __init__(self, name: str, flammable: bool = False, description: Optional[str] = None, value: float = 0.0, fire_behavior: Optional[FireBehavior] = None):
        self.name = name
        self.flammable = flammable
        self.description = description or ""
        self.value = value  # monetary or replacement value in arbitrary units
        self.fire_behavior = fire_behavior

    def __repr__(self):
        return f"<Item name={self.name}, flammable={self.flammable}, value={self.value}>"

    def contributes_to_fire(self) -> bool:
        """Returns True if the item can increase fire risk."""
        return self.flammable

    def heat_release(self, burn_time: float) -> float:
        if self.fire_behavior:
            return self.fire_behavior.heat_release(burn_time)
        return 0.0

class CoverMaterialItem(Item):
    """
    Represents a surface-mounted cover material (e.g., MDF layer, fabric, foam) that contributes fuel and heat to fire.
    Typically applied to walls, ceilings, or floors.
    """

    def __init__(self,
                 name: str,
                 fire_behavior: FireBehavior,
                 flammable: bool = True,
                 description: Optional[str] = None):
        super().__init__(name=name, flammable=flammable, description=description)
        self.fire_behavior = fire_behavior

    def get_fire_properties(self) -> dict:
        """
        Returns fire-related metrics specific to surface covers.
        """
        return {
            "flammable": self.flammable,
            "material": self.fire_behavior.material.name,
            "mass_kg": self.fire_behavior.mass_kg,
            "surface_bound": True,
            "fire_behavior": self.fire_behavior
        }

    def __repr__(self):
        return (f"<CoverMaterialItem name={self.name}, flammable={self.flammable}, "
                f"{repr(self.fire_behavior)}>")

COVER_MATERIAL_ITEMS = {
    name: CoverMaterialItem(
        name=name,
        fire_behavior=FireBehavior(material, mass_kg=mass),
        flammable=True,
        description=f"{name} surface layer"
    )
    for name, (material, mass) in {
        "insulating fiberboard": (COVER_MATERIALS["insulating fiberboard"], 2.7),
        "medium density fiberboard": (COVER_MATERIALS["medium density fiberboard"], 3.0),
        "particle board": (COVER_MATERIALS["particle board"], 3.3),
        "gypsum plasterboard": (COVER_MATERIALS["gypsum plasterboard"], 4.5),
        "PVC on gypsum": (COVER_MATERIALS["PVC on gypsum"], 2.4),
        "paper on gypsum": (COVER_MATERIALS["paper on gypsum"], 1.8),
        "textile on gypsum": (COVER_MATERIALS["textile on gypsum"], 2.1),
        "textile on mineral wool": (COVER_MATERIALS["textile on mineral wool"], 2.4),
        "melamine-faced particle board": (COVER_MATERIALS["melamine-faced particle board"], 3.0),
        "expanded polystyrene": (COVER_MATERIALS["expanded polystyrene"], 1.2),
        "rigid polyurethane foam": (COVER_MATERIALS["rigid polyurethane foam"], 1.5),
        "wood panel, spruce": (COVER_MATERIALS["wood panel, spruce"], 3.6),
        "paper on particle board": (COVER_MATERIALS["paper on particle board"], 2.7),
    }.items()
}

class InventoryItem(Item):
    """
    Represents a typical object (e.g., furniture, appliance) that contributes fuel and heat to a fire.
    """

    def __init__(self,
                 name: str,
                 value: float,
                 fire_behavior: FireBehavior,
                 flammable: bool = True,
                 description: Optional[str] = None):
        super().__init__(name=name, flammable=flammable, description=description)
        self.value = value
        self.fire_behavior = fire_behavior

    def get_fire_properties(self) -> dict:
        """
        Returns fire-related metrics, including heat release rate based on FireBehavior.
        Assumes external fire loop will track and call .heat_release(burn_time).
        """
        return {
            "flammable": self.flammable,
            "material": self.fire_behavior.material.name,
            "mass_kg": self.fire_behavior.mass_kg,
            "heat_bonus": 0.5 * self.fire_behavior.material.flammability * self.fire_behavior.mass_kg,
            "fireload": self.fire_behavior.mass_kg * self.fire_behavior.material.flammability,
            "fire_behavior": self.fire_behavior  # allows deeper use in simulation
        }

    def __repr__(self):
        return (f"<InventoryItem name={self.name}, \nvalue={self.value}, \nflammable={self.flammable}, "
                f"{repr(self.fire_behavior)}>")

FURNITURE_ITEMS = {
    "wooden_chair": InventoryItem(
        name="wooden_chair",
        description="A standard solid wood chair.",
        flammable=True,
        value=150.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["wood"],
            mass_kg=8.0)
    ),
    "office_chair": InventoryItem(
        name="office_chair",
        description="A standard office plastic chair.",
        flammable=True,
        value=200.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["plastic"],
            mass_kg=6.0)
    ),
    "chesterfield_machester_wing_chair": InventoryItem(
        name="chesterfield_machester_wing_chair",
        description="Nice leather chair.",
        flammable=True,
        value=13550.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["leather_and_foam"],
            mass_kg=30.0)
    ),
    "decent_soffa": InventoryItem(
        name="decent_soffa",
        description="A decent soffa for 3.",
        flammable=True,
        value=2000.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["fabric"],
            mass_kg=30.0)
    ),
    "wooden_table": InventoryItem(
        name="wooden_table",
        description="A large solid oak table used for meetings.",
        flammable=True,
        value=250.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["wood"],
            mass_kg=15.0)
    ),
    "wooden_table_oak": InventoryItem(
        name="wooden_table_oak",
        description="A heavier wooden table made of oak.",
        flammable=True,
        value=6000.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["wood_oak"],
            mass_kg=40.0)
    ),
    "long_meeting_table": InventoryItem(
        name="long_meeting_table",
        description="Long meeting table needing multiple cubes.",
        flammable=True,
        value=5000.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["laminated_wood"],
            mass_kg=80.0)
    ),
    "wooden_bookshelf": InventoryItem(
        name="wooden_bookshelf",
        description="A tall shelf filled with flammable books and documents.",
        flammable=True,
        value=300.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["wood"],
            mass_kg=20.0)
    ),
    "reception_desk": InventoryItem(
        name="reception_desk",
        description="Counter for handling visitors.",
        flammable=True,
        value=10000.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["laminated_wood"],
            mass_kg=100.0)
    ),
    "wall-to-wall_carpet": InventoryItem(
        name="wall_carpet",
        description="Wall to wall carpet, covering entire floor surface.",
        flammable=True,
        value=2000.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["carpet_material"],
            mass_kg=10.0)
    )
}

FURNISHING_ITEMS = {
    "steinway_model_b_classic_grand_piano": InventoryItem(
        name="steinway_model_b_classic_grand_piano",
        description="Nice f-in piano.",
        flammable=True,
        value=1429000.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["wood"],
            mass_kg=364.0)
    ),
    "expensive_painting": InventoryItem(
        name="expensive_painting",
        description="Nice painting.",
        flammable=True,
        value=30000.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["paper"],
            mass_kg=10.0)
    ),
    "cheap_painting": InventoryItem(
        name="cheap_painting",
        description="Pretty nice painting.",
        flammable=True,
        value=500.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["paper"],
            mass_kg=10.0)
    )
}

OFFICE_SUPPLY_ITEMS = {
    "copy_machine": InventoryItem(
        name="copy_machine",
        description="A multifunction printer/copier with plastic and paper components.",
        flammable=True,
        value=1200.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["plastic"],
            mass_kg=40.0)
    ),
    "paper_boxes": InventoryItem(
        name="paper_boxes",
        description="Cardboard boxes filled with reams of printer paper.",
        flammable=True,
        value=50.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["paper"],
            mass_kg=10.0)
    ),
    "toner_cartridges": InventoryItem(
        name="toner_cartridges",
        description="Box of replacement toner cartridges, plastic and powder-based.",
        flammable=True,
        value=300.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["plastic"],
            mass_kg=4.0)
    ),
    "shipping_boxes": InventoryItem(
        name="shipping_boxes",
        description="Flattened corrugated cardboard shipping boxes stacked against the wall.",
        flammable=True,
        value=20.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["paper"],  # Cardboard often modeled similarly
            mass_kg=6.0)
    ),
    "old_files_archive": InventoryItem(
        name="old_files_archive",
        description="Banker boxes filled with archived paper records.",
        flammable=True,
        value=200.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["paper"],
            mass_kg=15.0)
    ),
    "plastic_shelves": InventoryItem(
        name="plastic_shelves",
        description="Plastic shelving unit holding office supplies.",
        flammable=True,
        value=80.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_ITEMS["plastic"],
            mass_kg=12.0)
    )
}

class MiscellaniousItemsGroup(Item):
    """
    Represents a generic set of unidentified items.
    Used for populating the cubes with additional flammable objects.
    Main purpose is to increase heat output or prolong burning in simulation.
    """

    def __init__(self,
                 name: str,
                 value: float,
                 fire_behavior: FireBehavior,
                 flammable: bool = True,
                 description: Optional[str] = None):
        super().__init__(name=name, flammable=flammable, description=description)
        self.value = value
        self.fire_behavior = fire_behavior

    def get_fire_properties(self) -> dict:
        """
        Returns fire-related metrics, including heat release rate based on FireBehavior.
        Assumes external fire loop will track and call .heat_release(burn_time).
        """
        return {
            "flammable": self.flammable,
            "material": self.fire_behavior.material.name,
            "mass_kg": self.fire_behavior.mass_kg,
            "heat_bonus": 0.5 * self.fire_behavior.material.flammability * self.fire_behavior.mass_kg, # Obsolete?
            "fireload": self.fire_behavior.mass_kg * self.fire_behavior.material.flammability, # Obsolete?
            "fire_behavior": self.fire_behavior  # Currently used.
        }

    def __repr__(self):
        return (f"<MiscellaniousItemsGroup name={self.name}, \nvalue={self.value}, \nflammable={self.flammable}, "
                f"{repr(self.fire_behavior)}>")

MISCELLANIOUS_ITEMS_GROUP = {
    "low_cost_small_set": InventoryItem(
        name="low_cost_small_set",
        description="A set of items with low cost values and a low sum of total_mass.",
        flammable=True,
        value=1000.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_MISCELLANIOUS_SETS["medium_hot_and_porous"],
            mass_kg=50.0)
    ),
    "low_cost_medium_set": InventoryItem(
        name="low_cost_medium_set",
        description="A set of items with low cost values and a medium sum of total_mass.",
        flammable=True,
        value=4000.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_MISCELLANIOUS_SETS["medium_hot_and_medium_dense"],
            mass_kg=200.0)
    ),
    "low_cost_large_set": InventoryItem(
        name="low_cost_large_set",
        description="A set of items with low cost values and a high sum of total_mass.",
        flammable=True,
        value=4000.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_MISCELLANIOUS_SETS["medium_hot_and_medium_dense"],
            mass_kg=400.0)
    ),
    "medium_cost_small_set": InventoryItem(
        name="medium_cost_small_set",
        description="A set of items with medium cost values and a low sum of total_mass.",
        flammable=True,
        value=3000.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_MISCELLANIOUS_SETS["medium_hot_and_medium_dense"],
            mass_kg=50.0)
    ),
    "medium_cost_medium_set": InventoryItem(
        name="medium_cost_medium_set",
        description="A set of items with medium cost values and a medium sum of total_mass.",
        flammable=True,
        value=5000.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_MISCELLANIOUS_SETS["medium_hot_and_medium_dense"],
            mass_kg=200.0)
    ),
    "medium_cost_large_set": InventoryItem(
        name="medium_cost_large_set",
        description="A set of items with medium cost values and a high sum of total_mass.",
        flammable=True,
        value=7000.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_MISCELLANIOUS_SETS["medium_hot_and_medium_dense"],
            mass_kg=400.0)
    ),
    "high_cost_small_set": InventoryItem(
        name="high_cost_small_set",
        description="A set of items with high cost values and a low sum of total_mass.",
        flammable=True,
        value=6000.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_MISCELLANIOUS_SETS["medium_hot_and_medium_dense"],
            mass_kg=50.0)
    ),
    "high_cost_medium_set": InventoryItem(
        name="high_cost_medium_set",
        description="A set of items with high cost values and a medium sum of total_mass.",
        flammable=True,
        value=15000.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_MISCELLANIOUS_SETS["medium_hot_and_medium_dense"],
            mass_kg=200.0)
    ),
    "high_cost_large_set": InventoryItem(
        name="high_cost_large_set",
        description="A set of items with high cost values and a high sum of total_mass.",
        flammable=True,
        value=30000.0,
        fire_behavior=FireBehavior(
            material=MATERIALS_FOR_MISCELLANIOUS_SETS["medium_hot_and_medium_dense"],
            mass_kg=400.0)
    )
}

class ProbabilisticDeviceMixin:
    """
    Opt‑in utility for classes that want per-device probabilistic parameters.
    Provides:
      - enable_probabilistic(rng=None)
      - disable_probabilistic()
      - reset_probabilistic_params()
      - _ensure_samplers()

    Subclasses must implement:
      - _build_samplers(self, rng): create sampler callables and store them on self
      - _redraw_once(self): draw one-shot samples for the current incident/run
    """
    probabilistic: bool = False

    def enable_probabilistic(self, rng: "np.random.Generator" = None):
        self.probabilistic = True
        # preserve/chain an RNG if one already exists
        self._rng = rng or getattr(self, "_rng", None) or np.random.default_rng()
        self._build_samplers(self._rng)
        # clear any cached draws so they'll be re-drawn on demand
        for attr in dir(self):
            if attr.startswith("_sampled_"):
                setattr(self, attr, None)

    def disable_probabilistic(self):
        self.probabilistic = False
        # keep RNG but drop samplers & cached draws
        for attr in ("_max_burn_time_sampler", "_trigger_temp_sampler"):
            if hasattr(self, attr):
                setattr(self, attr, None)
        for attr in list(a for a in dir(self) if a.startswith("_sampled_")):
            setattr(self, attr, None)

    def reset_probabilistic_params(self):
        """Redraw one-shot samples for the current incident/run."""
        if not getattr(self, "probabilistic", False):
            return
        self._ensure_samplers()
        self._redraw_once()

    def _ensure_samplers(self):
        """Lazy builder used by sampling accessors."""
        if not getattr(self, "probabilistic", False):
            return
        need_build = False
        # Heuristic: if subclass hasn't created any sampler attrs yet, (re)build
        for name in ("_max_burn_time_sampler", "_trigger_temp_sampler"):
            if hasattr(self, name) and getattr(self, name) is None:
                need_build = True
        if need_build or not hasattr(self, "_rng"):
            self.enable_probabilistic(getattr(self, "_rng", None))

    # --- abstract hooks to implement in subclass ---
    def _build_samplers(self, rng):
        raise NotImplementedError

    def _redraw_once(self):
        raise NotImplementedError

import random

class FireSafetyItem(Item, ABC):
    def __init__(self,
                 name: str,
                 description: Optional[str],
                 flammable: bool,
                 value: float,
                 fire_behavior: Optional[FireBehavior],
                 trigger_temp: float,
                 reliability: float = 1.0,
                 active: bool = True,
                 last_maintenance: Optional[int] = None,
                 effect_radius: float = 4.0):  # NEW
        super().__init__(name=name, flammable=flammable, description=description)
        self.value = value
        self.fire_behavior = fire_behavior

        self.trigger_temp = trigger_temp
        self.triggered = False
        self.reliability = reliability
        self.active = active
        self.last_maintenance = last_maintenance

        self.effect_radius = effect_radius  # NEW

    @abstractmethod
    def respond_to_fire(self, fire_state: "FireState", cube: "Cube") -> None:
        """
        Defines how the device responds to fire. Subclasses must implement.
        """
        pass

class Sprinkler(ProbabilisticDeviceMixin, FireSafetyItem):
    """
    Sprinkler with optional probabilistic trigger temperature and time scaling.
    If probabilistic=True, this instance draws per-device values once and reuses them.
    """
    def __init__(self,
                 suppression_rate: float = 20.0,
                 probabilistic: bool = False,
                 **kwargs):
        super().__init__(**kwargs)
        self.suppression_rate = suppression_rate
        self.default_max_burn_time = 30.0

        # Sampler placeholders & cached draws
        self._max_burn_time_sampler = None
        self._trigger_temp_sampler = None
        self._sampled_max_burn_time = None
        self._sampled_trigger_temp = None

        # Opt-in
        if probabilistic:
            self.enable_probabilistic()

    # ---- mixin hooks ----
    def _build_samplers(self, rng):
        # import here to avoid circulars
        self._max_burn_time_sampler = normal_sampler(
            mean=getattr(self, "default_max_burn_time", 30.0),
            std=20.0,
            rng=rng
        )
        self._trigger_temp_sampler = normal_sampler(
            mean=float(self.trigger_temp),
            std=1.0,
            rng=rng
        )

    def _redraw_once(self):
        # Draw once per incident; clamp to safe ranges
        self._sampled_max_burn_time = max(1.0, float(self._max_burn_time_sampler(size=1)[0]))
        self._sampled_trigger_temp  = max(0.0, float(self._trigger_temp_sampler(size=1)[0]))

    # ---- convenience accessors ----
    def _max_burn_time_sample(self) -> float:
        if not getattr(self, "probabilistic", False):
            return getattr(self, "default_max_burn_time", 30.0)
        self._ensure_samplers()
        if self._sampled_max_burn_time is None:
            self.reset_probabilistic_params()
        return float(self._sampled_max_burn_time)

    def _trigger_temp_sample(self) -> float:
        if not getattr(self, "probabilistic", False):
            return float(self.trigger_temp)
        self._ensure_samplers()
        if self._sampled_trigger_temp is None:
            self.reset_probabilistic_params()
        return float(self._sampled_trigger_temp)

    # ---- simulation callback ----
    def respond_to_fire(self, fire_state: "FireState", cube: "Cube", verbose: bool = False) -> None:
        if not self.active:
            return
        if cube.air_temp < self._trigger_temp_sample():
            return
        if not self.triggered:
            import random
            if random.random() > self.reliability:
                return
            self.triggered = True
            if verbose:
                print(f"🚨 Sprinkler triggered at {cube.coordinate.as_tuple()} (T={cube.air_temp:.1f}°C)")
        max_bt = self._max_burn_time_sample()
        progression = fire_state.burn_time / max_bt
        suppression = self.suppression_rate * max(0.0, 1.0 - progression)
        fire_state.heat = max(fire_state.heat - suppression, 20.0)

class SmokeAlarm(ProbabilisticDeviceMixin, FireSafetyItem):
    """
    Smoke alarm with optional probabilistic trigger temperature and detection lag.
    If probabilistic=True, this instance draws per-device values once and reuses them
    for the whole incident/run.
    """
    def __init__(self,
                 detects_fire: bool = True,
                 probabilistic: bool = False,
                 **kwargs):
        super().__init__(**kwargs)
        self.detects_fire = detects_fire

        # Defaults (parallel to Sprinkler’s default_max_burn_time idea)
        self.default_detection_lag_s = 5.0  # seconds until alarm actually trips after threshold

        # Sampler placeholders & cached draws
        self._trigger_temp_sampler = None
        self._detection_lag_sampler = None
        self._sampled_trigger_temp = None
        self._sampled_detection_lag = None

        # Per-incident threshold-cross time bookkeeping
        self._threshold_cross_time = None  # measured in sim ticks/seconds (same unit as sim time)

        if probabilistic:
            self.enable_probabilistic()

    # ---- mixin hooks ----
    def _build_samplers(self, rng):
        # Same pattern as Sprinkler: normal draws, then clamp in _redraw_once
        self._trigger_temp_sampler = normal_sampler(
            mean=float(self.trigger_temp),
            std=1.0,
            rng=rng
        )
        # Small positive delay; normal is fine here (no lognormal util available),
        # we clamp at redraw.
        self._detection_lag_sampler = normal_sampler(
            mean=float(getattr(self, "default_detection_lag_s", 5.0)),
            std=2.0,
            rng=rng
        )

    def _redraw_once(self):
        # Draw once per run and clamp
        self._sampled_trigger_temp  = max(0.0, float(self._trigger_temp_sampler(size=1)[0]))
        # allow zero/short lag but not negative
        self._sampled_detection_lag = max(0.0, float(self._detection_lag_sampler(size=1)[0]))
        # reset threshold-cross bookeeping for this run
        self._threshold_cross_time = None

    # ---- convenience accessors ----
    def _trigger_temp_sample(self) -> float:
        if not getattr(self, "probabilistic", False):
            return float(self.trigger_temp)
        self._ensure_samplers()
        if self._sampled_trigger_temp is None:
            self.reset_probabilistic_params()
        return float(self._sampled_trigger_temp)

    def _detection_lag_sample(self) -> float:
        if not getattr(self, "probabilistic", False):
            return float(getattr(self, "default_detection_lag_s", 5.0))
        self._ensure_samplers()
        if self._sampled_detection_lag is None:
            self.reset_probabilistic_params()
        return float(self._sampled_detection_lag)

    # ---- simulation callback ----
    def respond_to_fire(self, fire_state: "FireState", cube: "Cube", verbose: bool = False) -> None:
        if not self.active or not self.detects_fire or self.triggered:
            return

        # Check threshold with sampled temperature
        if cube.air_temp >= self._trigger_temp_sample():
            # Start timing once we first cross threshold
            if self._threshold_cross_time is None:
                self._threshold_cross_time = getattr(fire_state, "burn_time", 0)

            # Require threshold to be held for at least the sampled lag
            t_now = getattr(fire_state, "burn_time", 0)
            if (t_now - self._threshold_cross_time) >= self._detection_lag_sample():
                # Reliability gate (same as today)
                import random
                if random.random() <= self.reliability:
                    self.triggered = True
                    if verbose:
                        print(f"🚨 Smoke alarm triggered at {cube.coordinate.as_tuple()} "
                              f"(T={cube.air_temp:.1f}°C, lag={self._detection_lag_sample():.1f}s)")
        else:
            # Fell below threshold → reset hold timer
            self._threshold_cross_time = None

FIRE_SAFETY_ITEMS = {
    "sprinkler_a1": Sprinkler(
        name="Ceiling Sprinkler A1",
        description="Ceiling-mounted sprinkler head",
        flammable=False,
        value=600.0,
        fire_behavior=None,
        trigger_temp=68.0,
        suppression_rate=0.4,
        reliability=0.95,
        active=True,
        last_maintenance=50,
        effect_radius=4.0
    ),
    "smoke_alarm_x1": SmokeAlarm(
        name="Smoke Alarm X1",
        description="Wall-mounted smoke alarm unit",
        flammable=False,
        value=120.0,
        fire_behavior=None,
        trigger_temp=57.0,
        reliability=0.98,
        active=True,
        last_maintenance=45,
        effect_radius=6.0
    )
}

class AccessPanel(Item):
    def __init__(self,
                 name: str,
                 flammable: bool,
                 description: str,
                 access_level_requirement: int,  # [1, 3]
                 value: float = 0.0,
                 active=True):
        super().__init__(
            name=name,
            flammable=flammable,
            description=description,
            value=value
        )
        self.access_level_requirement = access_level_requirement
        self.active = active

    def determine_access(self, access_card):
        return access_card.access_level >= self.access_level_requirement

class AccessCard(Item):
    def __init__(self,
                 name: str,
                 flammable: bool,
                 description: str,
                 access_level: int, # [1, 3] - Higher level => better access.
                 value: float = 0.0,
                 active=True):
        super().__init__(
            name=name,
            flammable=flammable,
            description=description,
            value=value)
        self.access_level = access_level
        self.active = active

ACCESS_CARDS = {
    "access_card_level_1": AccessCard(
        name="access_card_level_1", description="Low-level access in building", flammable=False, access_level=1),
    "access_card_level_2": AccessCard(
        name="access_card_level_2", description="Medium-level access in building", flammable=False, access_level=2),
    "access_card_level_3": AccessCard(
        name="access_card_level_3", description="High-level access in building", flammable=False, access_level=3),
}

ACCESS_PANELS = {
    "panel_lvl_3": AccessPanel(
        name="panel_lvl_3", flammable=False, description="High security access",
        access_level_requirement=3),
    "panel_lvl_2": AccessPanel(
        name="panel_lvl_2", flammable=False, description="Medium security access",
        access_level_requirement=2),
    "panel_lvl_1": AccessPanel(
        name="panel_lvl_1", flammable=False, description="Low security access",
        access_level_requirement=1)
}

class BuildingComponent:
    """Base class for all building model nodes."""
    def __init__(self, node_id: int):
        self.node_id = node_id
        self.items: List[object] = []  # Can be customized per application

# Default cube air temperature.
DEFAULT_CUBE_TEMPERATURE = 20.0

# Default value for undegraded surfaces.
DEFAULT_DEGRADATION_VALUE = 100.0

# Default fallback wall materials.
DEFAULT_FALLBACK_WALL_STRUCTURAL_MATERIAL = STRUCTURAL_MATERIALS["brick"]
DEFAULT_FALLBACK_WALL_COVER_MATERIAL = COVER_MATERIAL_ITEMS["particle board"]

# Default fallback floor materials.
DEFAULT_FALLBACK_FLOOR_STRUCTURAL_MATERIAL = STRUCTURAL_MATERIALS["concrete"]
DEFAULT_FALLBACK_FLOOR_COVER_MATERIAL = COVER_MATERIAL_ITEMS["paper on particle board"]

# Default fallback ceiling materials.
DEFAULT_FALLBACK_CEILING_STRUCTURAL_MATERIAL = STRUCTURAL_MATERIALS["concrete"]
DEFAULT_FALLBACK_CEILING_COVER_MATERIAL = COVER_MATERIAL_ITEMS["textile on gypsum"]

# Default fallback roof materials.
DEFAULT_FALLBACK_ROOF_STRUCTURAL_MATERIAL = STRUCTURAL_MATERIALS["metal"]
DEFAULT_FALLBACK_ROOF_COVER_MATERIAL = COVER_MATERIAL_ITEMS["textile on mineral wool"]

class Cube(BuildingComponent):
    # Being treated as 5m^3 -> area \approx 1.7m.
    def __init__(self, node_id: int, coordinate: Coordinate):
        super().__init__(node_id)
        self.coordinate = coordinate

        # Six surfaces
        self.left_wall: Optional['Wall'] = None
        self.right_wall: Optional['Wall'] = None
        self.front_wall: Optional['Wall'] = None
        self.back_wall: Optional['Wall'] = None
        self.floor: Optional['FloorSurface'] = None
        self.ceiling: Optional['CeilingSurface'] = None
        self.roof: Optional['CeilingRoof'] = None

        # 🌡️ Persistent air temperature (°C or arbitrary unit)
        self.air_temp: float = DEFAULT_CUBE_TEMPERATURE  # ambient room temperature

        # 🧱 Room assignment
        self.room: Optional["Room"] = None

        # Optional local flag if you want the cube to carry its own state
        # (your simulator can also keep this in fire_status instead).
        self.is_on_fire: bool = False

    def get_all_components(self) -> List[BuildingComponent]:
        return [
            comp for comp in [
                self.left_wall, self.right_wall,
                self.front_wall, self.back_wall,
                self.floor, self.ceiling, self.roof
            ] if comp is not None
        ]

    def get_all_surfaces(self) -> List[BuildingComponent]:
        return [
            comp for comp in [
                self.left_wall, self.right_wall,
                self.front_wall, self.back_wall,
                self.floor, self.ceiling, self.roof
            ] if comp is not None and not isinstance(comp, Cube)
        ]

    def get_items_by_location_and_type(self) -> dict:
        from collections import defaultdict

        result = defaultdict(lambda: defaultdict(list))

        # Items directly in the cube
        if hasattr(self, "items"):
            for item in self.items:
                key = type(item).__name__
                result["cube"][key].append(item)

        # Items on surfaces
        for surface_name in ["left_wall", "right_wall", "front_wall", "back_wall", "floor", "ceiling", "roof"]:
            surface = getattr(self, surface_name)
            if surface and hasattr(surface, "items"):
                for item in surface.items:
                    key = type(item).__name__
                    result[surface_name][key].append(item)

        return dict(result)

    # --------- New helpers for fire-state derivation ---------

    def iter_all_items(self):
        """Yield all items located in the cube and attached to any surface."""
        if hasattr(self, "items"):
            for it in self.items:
                yield it
        for s in self.get_all_surfaces():
            for it in getattr(s, "items", []) or []:
                yield it

    def _fb_active(self, fb, epsilon_kJ: float = 1e-3) -> bool:
        """
        True iff the FireBehavior is currently burning or still releasing energy.
        Uses a small epsilon on latest_heat_output to avoid flicker on tiny tails.
        """
        if not fb:
            return False
        if getattr(fb, "is_ignited", False):
            return True
        if getattr(fb, "latest_heat_output", 0.0) > epsilon_kJ:
            return True
        rel = float(getattr(fb, "released_energy", 0.0))
        tot = float(getattr(fb, "total_energy", 0.0))
        return 0.0 < rel < tot

    def has_active_fire(self, epsilon_kJ: float = 1e-3) -> bool:
        for s in self.get_all_surfaces():
            cover = getattr(s, "cover_material", None)
            fb = getattr(cover, "fire_behavior", None) if cover else None
            if fb and fb.is_active(epsilon_kJ):
                return True
        for it in self.iter_all_items():
            fb = getattr(it, "fire_behavior", None)
            if fb and fb.is_active(epsilon_kJ):
                return True
        return False

    def refresh_fire_flag(self, epsilon_kJ: float = 1e-3, verbose: bool = False) -> bool:
        new_state = self.has_active_fire(epsilon_kJ)
        if self.is_on_fire != new_state:
            if verbose:
                print(f"[Cube.refresh_fire_flag] {self.coordinate.as_tuple()} → {new_state}")
            self.is_on_fire = new_state
        return new_state


    def extinguish_inactive_surfaces(self, epsilon_kJ: float = 1e-3):
        """
        Ask each surface to clear its own ignition flag if its cover is no longer active.
        """
        for s in self.get_all_surfaces():
            if hasattr(s, "extinguish_cover_material"):
                s.extinguish_cover_material()

class Wall(BuildingComponent):
    """Wall on one side of a cube, may be interior or exterior."""
    def __init__(self, node_id: int, cube: Cube, direction: str,
                 is_exterior: bool = False,
                 hollow: bool = False,
                 structure_material: Material = DEFAULT_FALLBACK_WALL_STRUCTURAL_MATERIAL,
                 cover_material: CoverMaterialItem = DEFAULT_FALLBACK_WALL_COVER_MATERIAL):
        super().__init__(node_id)
        self.cube = cube
        self.direction = direction
        self.is_exterior = is_exterior
        self.hollow = hollow

        self.structure_material = structure_material
        self.degradation = DEFAULT_DEGRADATION_VALUE

        self.cover_material = cover_material
        self.time_above_ignition_temp: float = 0.0  # seconds
        self.is_ignited: bool = False

        self.surface_neighbor = None
        setattr(cube, f"{direction}_wall", self)

    def extinguish_cover_material(self, epsilon_kJ: float = 1e-3):
        """
        Sync this surface's ignition state with its cover's FireBehavior.
        A cover is considered active only if it is currently ignited OR emitted
        measurable heat this tick. Residual unburned fuel alone does not count.
        """
        fb = getattr(self.cover_material, "fire_behavior", None)
        if not fb:
            self.is_ignited = False
            self.time_above_ignition_temp = 0.0
            return

        # Mirror exposure timer for UI/debug
        self.time_above_ignition_temp = getattr(fb, "time_above_ignition_temp", 0.0)

        # Determine activity with the new rule
        if hasattr(fb, "is_active"):
            active = fb.is_active(epsilon_kJ)
        else:
            active = bool(getattr(fb, "is_ignited", False) or
                          (getattr(fb, "latest_heat_output", 0.0) > epsilon_kJ))

        if not active:
            self.is_ignited = False
            # Require fresh continuous exposure for any re-ignition
            self.time_above_ignition_temp = 0.0


class FloorSurface(BuildingComponent):
    def __init__(self, node_id: int, cube: Cube,
                 hollow: bool = False,
                 structure_material: Material = DEFAULT_FALLBACK_FLOOR_STRUCTURAL_MATERIAL,
                 cover_material: CoverMaterialItem = DEFAULT_FALLBACK_FLOOR_COVER_MATERIAL):
        super().__init__(node_id)
        self.cube = cube
        self.hollow = hollow

        self.structure_material = structure_material
        self.degradation = DEFAULT_DEGRADATION_VALUE

        self.cover_material = cover_material
        self.time_above_ignition_temp: float = 0.0  # seconds
        self.is_ignited: bool = False

        self.surface_neighbor = None
        cube.floor = self

    def extinguish_cover_material(self, epsilon_kJ: float = 1e-3):
        """
        Sync this surface's ignition state with its cover's FireBehavior.
        A cover is considered active only if it is currently ignited OR emitted
        measurable heat this tick. Residual unburned fuel alone does not count.
        """
        fb = getattr(self.cover_material, "fire_behavior", None)
        if not fb:
            self.is_ignited = False
            self.time_above_ignition_temp = 0.0
            return

        # Mirror exposure timer for UI/debug
        self.time_above_ignition_temp = getattr(fb, "time_above_ignition_temp", 0.0)

        # Determine activity with the new rule
        if hasattr(fb, "is_active"):
            active = fb.is_active(epsilon_kJ)
        else:
            active = bool(getattr(fb, "is_ignited", False) or
                          (getattr(fb, "latest_heat_output", 0.0) > epsilon_kJ))

        if not active:
            self.is_ignited = False
            # Require fresh continuous exposure for any re-ignition
            self.time_above_ignition_temp = 0.0


class CeilingSurface(BuildingComponent):
    def __init__(self, node_id: int, cube: Cube,
                 hollow: bool = False,
                 structure_material: Material = DEFAULT_FALLBACK_CEILING_STRUCTURAL_MATERIAL,
                 cover_material: CoverMaterialItem = DEFAULT_FALLBACK_CEILING_COVER_MATERIAL):
        super().__init__(node_id)
        self.cube = cube
        self.hollow = hollow

        self.structure_material = structure_material
        self.degradation = DEFAULT_DEGRADATION_VALUE

        self.cover_material = cover_material
        self.time_above_ignition_temp: float = 0.0  # seconds
        self.is_ignited: bool = False

        self.surface_neighbor = None
        cube.ceiling = self

    def extinguish_cover_material(self, epsilon_kJ: float = 1e-3):
        """
        Sync this surface's ignition state with its cover's FireBehavior.
        A cover is considered active only if it is currently ignited OR emitted
        measurable heat this tick. Residual unburned fuel alone does not count.
        """
        fb = getattr(self.cover_material, "fire_behavior", None)
        if not fb:
            self.is_ignited = False
            self.time_above_ignition_temp = 0.0
            return

        # Mirror exposure timer for UI/debug
        self.time_above_ignition_temp = getattr(fb, "time_above_ignition_temp", 0.0)

        # Determine activity with the new rule
        if hasattr(fb, "is_active"):
            active = fb.is_active(epsilon_kJ)
        else:
            active = bool(getattr(fb, "is_ignited", False) or
                          (getattr(fb, "latest_heat_output", 0.0) > epsilon_kJ))

        if not active:
            self.is_ignited = False
            # Require fresh continuous exposure for any re-ignition
            self.time_above_ignition_temp = 0.0


class CeilingRoof(BuildingComponent):
    def __init__(self, node_id: int, cube: Cube,
                 hollow: bool = False,
                 structure_material: Material = DEFAULT_FALLBACK_ROOF_STRUCTURAL_MATERIAL,
                 cover_material: CoverMaterialItem = DEFAULT_FALLBACK_ROOF_COVER_MATERIAL):
        super().__init__(node_id)
        self.cube = cube
        self.hollow = hollow

        self.structure_material = structure_material
        self.degradation = DEFAULT_DEGRADATION_VALUE

        self.cover_material = cover_material
        self.time_above_ignition_temp: float = 0.0  # seconds
        self.is_ignited: bool = False

        self.surface_neighbor = None
        cube.roof = self

    def extinguish_cover_material(self, epsilon_kJ: float = 1e-3):
        """
        Sync this surface's ignition state with its cover's FireBehavior.
        A cover is considered active only if it is currently ignited OR emitted
        measurable heat this tick. Residual unburned fuel alone does not count.
        """
        fb = getattr(self.cover_material, "fire_behavior", None)
        if not fb:
            self.is_ignited = False
            self.time_above_ignition_temp = 0.0
            return

        # Mirror exposure timer for UI/debug
        self.time_above_ignition_temp = getattr(fb, "time_above_ignition_temp", 0.0)

        # Determine activity with the new rule
        if hasattr(fb, "is_active"):
            active = fb.is_active(epsilon_kJ)
        else:
            active = bool(getattr(fb, "is_ignited", False) or
                          (getattr(fb, "latest_heat_output", 0.0) > epsilon_kJ))

        if not active:
            self.is_ignited = False
            # Require fresh continuous exposure for any re-ignition
            self.time_above_ignition_temp = 0.0

from typing import Optional, Tuple

class BuildingAccessory(Item):
    def __init__(self,
                 name: str,
                 description: Optional[str],
                 flammable: bool,
                 value: float,
                 fire_behavior: Optional[FireBehavior],
                 access_type: str,
                 is_open: bool = False,
                 is_locked: bool = False,
                 is_blocked: bool = False,
                 leads_to: Optional[Tuple[int, int, int]] = None,
                 is_exit: bool = False,
                 auto_close: bool = False):
        super().__init__(name, flammable, description, value, fire_behavior)
        self.access_type = access_type  # e.g., "door", "window", "ladder"
        self.is_open = is_open
        self.is_locked = is_locked
        self.is_blocked = is_blocked
        self.leads_to = leads_to
        self.is_exit = is_exit
        self.auto_close = auto_close

    def allows_passage(self) -> bool:
        return self.is_open and not self.is_blocked

    def open(self):
        if not self.is_locked and not self.is_blocked:
            self.is_open = True

    def close(self):
        if not self.is_blocked:
            self.is_open = False

    def toggle(self):
        if self.is_open:
            self.close()
        else:
            self.open()

    def __repr__(self):
        return (f"<BuildingAccessory name={self.name}, type={self.access_type}, "
                f"open={self.is_open}, locked={self.is_locked}, blocked={self.is_blocked}>")

class Door(BuildingAccessory):
    def __init__(self,
                 name: str,
                 description: Optional[str],
                 flammable: bool,
                 value: float,
                 fire_behavior: Optional[FireBehavior],
                 is_open: bool = False,
                 is_locked: bool = False,
                 is_blocked: bool = False,
                 leads_to: Optional[Tuple[int, int, int]] = None,
                 is_exit: bool = False,
                 auto_close: bool = False,
                 access_panel: Optional[object] = None):
        super().__init__(
            name=name,
            description=description,
            flammable=flammable,
            value=value,
            fire_behavior=fire_behavior,
            access_type="door",
            is_open=is_open,
            is_locked=is_locked,
            is_blocked=is_blocked,
            leads_to=leads_to,
            is_exit=is_exit,
            auto_close=auto_close
        )
        self.access_panel = access_panel # Hold requirement logic for opening door.

    def __repr__(self):
        return (f"<BuildingAccessory name={self.name}, type={self.access_type}, "
                f"open={self.is_open}, locked={self.is_locked}, blocked={self.is_blocked}>"
                f"access_panel={self.access_panel}")

class Window(BuildingAccessory):
    def __init__(self,
                 name: str,
                 description: Optional[str],
                 flammable: bool,
                 value: float,
                 fire_behavior: Optional[FireBehavior],
                 is_open: bool = False,
                 is_locked: bool = False,
                 is_blocked: bool = False,
                 leads_to: Optional[Tuple[int, int, int]] = None,
                 is_exit: bool = False):
        super().__init__(
            name=name,
            description=description,
            flammable=flammable,
            value=value,
            fire_behavior=fire_behavior,
            access_type="window",
            is_open=is_open,
            is_locked=is_locked,
            is_blocked=is_blocked,
            leads_to=leads_to,
            is_exit=is_exit,
            auto_close=False
        )

class Stairs(BuildingAccessory):
    def __init__(self,
                 name: str = "Stairs",
                 description: Optional[str] = "A staircase providing vertical access",
                 flammable: bool = False,
                 value: float = 1000.0,
                 fire_behavior: Optional[FireBehavior] = None,
                 leads_to: Optional[Tuple[int, int, int]] = None,
                 is_exit: bool = False,
                 is_blocked: bool = False):
        super().__init__(
            name=name,
            description=description,
            flammable=flammable,
            value=value,
            fire_behavior=fire_behavior,
            access_type="stairs",
            is_open=True,             # Always open
            is_locked=False,          # Not lockable
            is_blocked=is_blocked,
            leads_to=leads_to,
            is_exit=is_exit,
            auto_close=False
        )

    def __repr__(self):
        return f"<Stairs to={self.leads_to}, blocked={self.is_blocked}>"

DOORS = {
    "door_mediocre": Door(
        name="door_mediocre", description="A standard interior wooden door", flammable=True, value=200.0,
            fire_behavior=FireBehavior(material=MATERIALS_FOR_DOORS["solid_wood"], mass_kg=35.0)),
    "door_good": Door(
        name="door_good", description="Fire-rated steel emergency exit door", flammable=False, value=1200.0,
            fire_behavior=FireBehavior(material=MATERIALS_FOR_DOORS["steel_door"], mass_kg=80.0)),
    "dual_doors": Door(
        name="dual_doors", description="Fancy pancy doors with nice knobs.", flammable=True, value=4000.0,
            fire_behavior=FireBehavior(material=MATERIALS_FOR_DOORS["wood_oak"], mass_kg=70.0)),
    "main_entry_door": Door(
        name="main_entry_door", description="Door used for main entry to the facility.", flammable=False, value=10000.0,
            fire_behavior=FireBehavior(material=MATERIALS_FOR_DOORS["wood_oak"], mass_kg=100.0),
            is_exit=True)
}

WINDOWS = {
    "window_mediocre": Window(
        name="Hardwood Window", description="Window with hardwood frame", flammable=True, value=300.0,
            fire_behavior=FireBehavior(material=MATERIALS_FOR_WINDOWS["hardwood_frame"], mass_kg=15.0)),
    "window_good": Window(
        name="Reinforced Glass Window", description="Fire-resistant reinforced glass window", flammable=False, value=800.0,
            fire_behavior=FireBehavior(material=MATERIALS_FOR_WINDOWS["reinforced_glass"], mass_kg=25.0))
}

STAIRS = {
    "oak_stairs": Stairs(
        name="Oak Staircase", description="Heavy-duty oak staircase", flammable=True, value=14000.0,
            fire_behavior=FireBehavior(material=MATERIALS_FOR_STAIRS["oak_wood"], mass_kg=85.0))
}

class Room:
    def __init__(self, room_id: int, cubes: Set[Tuple[int, int, int]], model: Dict[Tuple[int, int, int], Cube]):
        self.room_id = room_id
        self.cube_coords = cubes
        self.model = model
        self.components: Set[BuildingComponent] = self._find_components()
        self.surfaces: Dict[str, List[BuildingComponent]] = self._group_surfaces()

    def _find_components(self) -> Set[BuildingComponent]:
        comps = set()
        for coord in self.cube_coords:
            cube = self.model.get(coord)
            if cube:
                comps.update(cube.get_all_components())
        return comps

    def _group_surfaces(self) -> Dict[str, List[BuildingComponent]]:
        """Group surfaces by type and direction using updated Cube structure."""
        grouped: Dict[str, List[BuildingComponent]] = {
            "floor": [], "ceiling": [], "roof": [],
            "walls_left": [], "walls_right": [],
            "walls_front": [], "walls_back": []
        }
        seen = set()

        for coord in self.cube_coords:
            cube = self.model[coord]

            # Map new surface fields to their grouping keys
            direction_map = {
                "walls_left": cube.left_wall,
                "walls_right": cube.right_wall,
                "walls_front": cube.front_wall,
                "walls_back": cube.back_wall,
                "floor": cube.floor,
                "ceiling": cube.ceiling,
                "roof": cube.roof
            }

            for key, comp in direction_map.items():
                if comp and comp.node_id not in seen:
                    seen.add(comp.node_id)
                    grouped[key].append(comp)

        return grouped

    def assign_material(self, surface_type: str, material: Material, only_non_hollow: bool = False):
        for surface in self.surfaces.get(surface_type, []):
            if not only_non_hollow or not getattr(surface, "hollow", False):
                surface.material = material

    def get_cubes_within_radius(self, origin: Tuple[int, int, int], radius: float) -> List[Cube]:
        """
        Return all cubes in this room within a given Euclidean radius of the origin cube.
        """
        def euclidean(a, b):
            return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5

        nearby = [
            self.model[coord]
            for coord in self.cube_coords
            if euclidean(coord, origin) <= radius
        ]
        return nearby


    def __repr__(self):
        return f"<Room ID={self.room_id}, Cubes={len(self.cube_coords)}, Components={len(self.components)}>"
