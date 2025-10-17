**Standard PC (Q35 + ICH9, 2009) – QEMU Virtual Machine Configuration**

---

## 1. Overview
| Item | Details |
|------|---------|
| **Model name** | **Standard PC (Q35 + ICH9, 2009)** |
| **Manufacturer** | QEMU (open‑source hypervisor) |
| **Chipset** | **Q35** (Intel P35/G35 family) + **ICH9** (Intel I/O Controller Hub 9) |
| **First introduced** | 2009 (the ICH9 chipset was released by Intel in 2009) |
| **Purpose** | General‑purpose x86‑64 virtual machine used for testing, development, CI, and desktop virtualization. |

---

## 2. Core Hardware Specification

| Category | Specification / Capability |
|----------|-----------------------------|
| **CPU** | Emulated x86‑64 CPUs (e.g., `qemu64`, `core2duo`, `host`); supports SMP, CPU flags, and KVM acceleration when available. |
| **Chipset** | Q35 (PCI‑Express root complex) + ICH9 (provides SATA, USB 2.0/3.0, PCI‑Express ports, HD‑audio, etc.). |
| **PCI‑Express** | Full PCI‑Express root port hierarchy; devices appear on bus `pcie.0`. |
| **USB** | ICH9‑USB controller provides: <br>• **UHCI** (USB 1.1) – 4 ports <br>• **OHCI** (USB 1.1) – 2 ports <br>• **EHCI** (USB 2.0) – 2 ports <br>• **XHCI** (USB 3.0) – optional via `-device qemu-xhci`. |
| **SATA / IDE** | ICH9‑AHCI controller (`ich9-ahci`) for SATA; legacy IDE controller also present for compatibility. |
| **Audio** | Intel HD‑Audio controller (`ich9-intel-hda`). |
| **Network** | VirtIO‑net, e1000, rtl8139, etc. (user‑selectable). |
| **Graphics** | Default VGA (QXL/Bochs) or VirtIO‑GPU; can attach a PCI‑Express GPU device. |
| **Memory** | Guest RAM is user‑defined (e.g., `-m 4G`). No hard‑coded limit beyond host resources. |
| **Storage** | Supports virtio‑blk, IDE, SATA, SCSI, and NVMe devices. |
| **Firmware** | Uses SeaBIOS (BIOS) by default; can be switched to OVMF (UEFI) with `-bios OVMF.fd`. |
| **Other peripherals** | PIC, PIT, HPET, ACPI, SMBus, LPC, and optional TPM. |

---

## 3. Typical QEMU Command Line (example)

```bash
qemu-system-x86_64 \
  -machine q35,accel=kvm \
  -cpu host \
  -smp 4 \
  -m 8G \
  -drive file=ubuntu.qcow2,if=virtio,format=qcow2 \
  -device ich9-intel-hda \
  -device ich9-ahci,id=ahci \
  -device ide-hd,bus=ahci.0,drive=drive0 \
  -device ich9-usb-ehci1,id=ehci \
  -device ich9-usb-uhci1,bus=ehci.0,masterbus=ehci.0,firstport=0 \
  -device ich9-usb-uhci2,bus=ehci.0,masterbus=ehci.0,firstport=2 \
  -device ich9-usb-uhci3,bus=ehci.0,masterbus=ehci.0,firstport=4 \
  -device ich9-usb-uhci4,bus=ehci.0,masterbus=ehci.0,firstport=6 \
  -netdev user,id=net0 -device e1000,netdev=net0 \
  -vga qxl \
  -display gtk,gl=on
```

*The command shows the Q35 machine, ICH9 USB/EHCI/UHCI devices, AHCI SATA, HD‑Audio, and a typical network/graphics setup.*

---

## 4. Virtualization Features

| Feature | Description |
|---------|-------------|
| **KVM acceleration** | `-accel kvm` (Linux) or `-accel hvf` (macOS) for near‑native performance. |
| **VirtIO devices** | High‑performance paravirtualized I/O (disk, network, balloon, GPU). |
| **Live migration** | Supported via QEMU’s `-incoming` / `-monitor` commands. |
| **Snapshot & QCOW2** | Disk snapshots, incremental backups, and copy‑on‑write images. |
| **PCI‑Passthrough** | Direct assignment of host PCIe devices to the VM (e.g., GPU). |
| **UEFI support** | OVMF firmware can be used for Secure Boot and modern OSes. |
| **Device hot‑plug** | PCIe hot‑plug, USB hot‑plug, and memory hot‑add (with appropriate guest drivers). |

---

## 5. References (URLs)

| # | Source | URL |
|---|--------|-----|
| 1 | Geekbench comparison page (shows the exact machine name) | <https://browser.geekbench.com/v4/cpu/compare/7520448?baseline=7517524> |
| 2 | UserBenchmark – component list for the Q35 + ICH9 VM | <https://www.userbenchmark.com/System/QEMU-Standard-PC-Q35---ICH9-2009/13204> |
| 3 | DriverIdentifier – driver scan results for the virtual hardware | <https://www.driveridentifier.com/scan/qemu-standard-pc-driver/desktop/AEF16FA5F1354B879AF5D1CA6AF08275> |
| 4 | OpenSUSE documentation – list of Q35 machine aliases (`pc-q35-2.x`) | <https://doc.opensuse.org/documentation/leap/archive/42.3/virtualization/html/book.virt/cha.qemu.running.html> |
| 5 | PiBenchmarks – benchmark data for the Q35 + ICH9 board | <https://pibenchmarks.com/board/Standard_PC_%28Q35_%5E_ICH9%2C_2009%29/> |
| 6 | Fuchsia QEMU source – `q35-chipset.cfg` (shows ICH9 device definitions) | <https://fuchsia.googlesource.com/third_party/qemu/+/v2.5.1/docs/q35-chipset.cfg> |
| 7 | QEMU development tree – another copy of `q35-chipset.cfg` | <https://git.zx2c4.com/qemu/tree/docs/q35-chipset.cfg?h=loongarch64&id=11eec063f29733395846ba756ecd544876ef6839> |

---

### Summary
The **Standard PC (Q35 + ICH9, 2009)** machine type in QEMU emulates a modern Intel chipset (Q35) combined with the ICH9 I/O hub, providing PCI‑Express, SATA, USB 2.0/3.0, HD‑Audio, and a full set of legacy devices. It is the default “pc-q35” machine used for most contemporary guest operating systems, offering high compatibility, KVM acceleration, and extensive paravirtualized I/O options. The specifications above capture the essential hardware layout and the key virtualization capabilities that make this configuration a versatile choice for developers, testers, and anyone needing a reliable x86‑64 virtual platform.
