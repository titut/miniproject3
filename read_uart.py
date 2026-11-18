#!/usr/bin/env python3
import argparse
import sys
import time
from pathlib import Path

import serial
from serial.tools import list_ports

STLINK_VID = 0x0483
STLINK_VCP_PID = 0x5740


def find_port() -> str | None:
    for port in list_ports.comports():
        if port.vid == STLINK_VID and port.pid == STLINK_VCP_PID:
            return port.device

    for port in list_ports.comports():
        description = f"{port.description} {port.manufacturer or ''}".upper()
        if "STM" in description or "ST-LINK" in description:
            return port.device

    for port in list_ports.comports():
        if "ACM" in port.device or "USB" in port.device:
            return port.device

    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read newline-delimited UART output from the STM32 board."
    )
    parser.add_argument(
        "-p",
        "--port",
        help="serial device, e.g. /dev/ttyACM0 (default: autodetect ST-Link VCP)",
    )
    parser.add_argument("-b", "--baud", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="prefix each line with seconds since the reader started",
    )
    parser.add_argument(
        "--log",
        type=Path,
        metavar="FILE",
        help="append decoded output to FILE",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list available serial ports and exit",
    )
    args = parser.parse_args()

    if args.list:
        ports = list_ports.comports()
        if not ports:
            print("No serial ports found.")
        for port in ports:
            print(f"{port.device}\t{port.description}\t{port.hwid}")
        return 0

    port = args.port or find_port()
    if not port:
        print(
            "No serial port found. Connect the board and pass --port /dev/ttyACM0.",
            file=sys.stderr,
        )
        return 1

    log = args.log.open("a", encoding="utf-8") if args.log else None
    started = time.monotonic()

    try:
        with serial.Serial(
            port,
            args.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=args.timeout,
        ) as ser:
            print(
                f"Reading {port} at {args.baud} baud. Ctrl+C to stop.",
                file=sys.stderr,
            )
            buffer = bytearray()

            while True:
                data = ser.read(ser.in_waiting or 1)
                if not data:
                    continue

                buffer.extend(data)
                while (index := buffer.find(b"\n")) >= 0:
                    raw = bytes(buffer[:index])
                    del buffer[: index + 1]
                    line = raw.rstrip(b"\r").decode("utf-8", "replace")
                    prefix = (
                        f"[{time.monotonic() - started:8.3f}] "
                        if args.timestamp
                        else ""
                    )
                    output = f"{prefix}{line}"
                    print(output, flush=True)
                    if log:
                        log.write(output + "\n")
                        log.flush()

    except KeyboardInterrupt:
        return 0
    except serial.SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        return 1
    finally:
        if log:
            log.close()


if __name__ == "__main__":
    raise SystemExit(main())
