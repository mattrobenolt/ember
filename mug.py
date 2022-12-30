import asyncio
import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable, Coroutine, Mapping, NoReturn, Tuple, TypeVar

from bleak import BleakClient, BleakScanner
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn

T = TypeVar("T")
Decoder = Callable[[bytearray], T]

console = Console()


async def main() -> Coroutine[Any, Any, NoReturn]:
    device = await BleakScanner.find_device_by_name(
        "Ember Ceramic Mug",
    )
    if device is None:
        console.log("not found")
        raise SystemExit(1)

    async with BleakClient(device) as client:
        mug = await get_mug(client)
        console.print(f"Mug: {mug.name.name}")
        console.log(mug)
        state = None
        temp_unit = mug.temp_unit
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
            expand=True,
        ) as progress:
            temp_total = mug.target_temp.temp.c
            if temp_unit == TempUnit.F:
                temp_total = mug.target_temp.temp.f
            temp_progress = progress.add_task("[red]Temp", total=temp_total)
            battery_progress = progress.add_task("[green]Battery", total=100)
            while True:
                mug = await get_mug(client)
                # console.log(mug)
                if temp_unit == TempUnit.C:
                    progress.update(
                        temp_progress, completed=mug.current_temp.temp.c
                    )
                else:
                    progress.update(
                        temp_progress, completed=mug.current_temp.temp.f
                    )
                progress.update(
                    battery_progress, completed=mug.battery.percent
                )
                if state != mug.liquid_state:
                    console.log(f"{state} -> {mug.liquid_state.name}")
                    state = mug.liquid_state
                match mug.liquid_state:
                    case LiquidState.Empty:
                        pass
                    case LiquidState.Heating:
                        pass
                    case LiquidState.Cooling:
                        pass
                    case LiquidState.Stable:
                        pass
                    case _:
                        console.log(mug)
                await asyncio.sleep(1)


async def read_char(client: BleakClient, k: str) -> Any:
    uuid, decoder = CHARACTERISTICS[k]
    return decoder(await client.read_gatt_char(uuid))


def get_uuid(char: str) -> Tuple[str, Decoder]:
    return CHARACTERISTICS[char][0]


dataclass = dataclass(frozen=True, slots=True, eq=False)


@dataclass
class Temp:
    c: float
    f: float


@dataclass
class CurrentTemp:
    temp: Temp


def decode_current_temp(data: bytearray) -> CurrentTemp:
    return CurrentTemp(read_temp(data))


def read_temp(data: bytearray) -> Temp:
    c = read_uint16(data) * 0.01
    return Temp(c, c_to_f(c))


@dataclass
class LiquidLevel:
    level: int


def decode_liquid_level(data: bytearray) -> LiquidLevel:
    return LiquidLevel(data[0])


@dataclass
class Battery:
    percent: int
    charging: bool


def decode_battery(data: bytearray) -> Battery:
    return Battery(data[0], bool(data[1]))


class LiquidState(IntEnum):
    Empty = 1
    Filling = 2
    Unknown = 3
    Cooling = 4
    Heating = 5
    Stable = 6


def decode_liquid_state(data: bytearray) -> LiquidState:
    return LiquidState(data[0])


@dataclass
class MugColor:
    r: int
    g: int
    b: int
    a: int


def decode_mug_color(data: bytearray) -> MugColor:
    return MugColor(data[0], data[1], data[2], data[3])


@dataclass
class MugName:
    name: str


def decode_mug_name(data: bytearray) -> MugName:
    return MugName(data.decode("ascii"))


@dataclass
class TargetTemp:
    temp: Temp


def decode_target_temp(data: bytearray) -> TargetTemp:
    return TargetTemp(read_temp(data))


class TempUnit(IntEnum):
    C = 0
    F = 1


def decode_temp_unit(data: bytearray) -> TempUnit:
    return TempUnit(data[0])


@dataclass
class Mug:
    name: MugName
    current_temp: CurrentTemp
    target_temp: TargetTemp
    temp_unit: TempUnit
    liquid_level: LiquidLevel
    battery: Battery
    liquid_state: LiquidState
    color: MugColor


async def get_mug(client: BleakClient) -> Mug:
    attrs = await asyncio.gather(
        *[
            asyncio.create_task(read_char(client, k))
            for k in (
                "mug-name",
                "current-temp",
                "target-temp",
                "temp-unit",
                "liquid-level",
                "battery",
                "liquid-state",
                "mug-color",
            )
        ]
    )
    return Mug(*attrs)


def temp_str(temp: Temp, unit: TempUnit) -> Tuple[float, str]:
    if unit == TempUnit.C:
        return temp.c, "C"
    return temp.f, "F"


def c_to_f(c: float | int) -> float:
    return (float(c) * 1.8) + 32


def read_uint16(data: bytearray) -> int:
    return struct.unpack("<h", data)[0]


CHARACTERISTICS: Mapping[str, Tuple[str, Decoder]] = {
    "mug-name": (
        "fc540001-236c-4c94-8fa9-944a3e5353fa",
        decode_mug_name,
    ),
    "current-temp": (
        "fc540002-236c-4c94-8fa9-944a3e5353fa",
        decode_current_temp,
    ),
    "target-temp": (
        "fc540003-236c-4c94-8fa9-944a3e5353fa",
        decode_target_temp,
    ),
    "temp-unit": (
        "fc540004-236c-4c94-8fa9-944a3e5353fa",
        decode_temp_unit,
    ),
    "liquid-level": (
        "fc540005-236c-4c94-8fa9-944a3e5353fa",
        decode_liquid_level,
    ),
    "battery": (
        "fc540007-236c-4c94-8fa9-944a3e5353fa",
        decode_battery,
    ),
    "liquid-state": (
        "fc540008-236c-4c94-8fa9-944a3e5353fa",
        decode_liquid_state,
    ),
    "mug-color": (
        "fc540014-236c-4c94-8fa9-944a3e5353fa",
        decode_mug_color,
    ),
}

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
