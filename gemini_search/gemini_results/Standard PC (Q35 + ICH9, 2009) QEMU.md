# Query: Standard PC (Q35 + ICH9, 2009) QEMU

**Response Time:** 14.89 seconds

QEMU's "Standard PC (Q35 + ICH9, 2009)" machine type emulates a modern personal computer architecture based on the Intel Q35 Express chipset with the ICH9 I/O Controller Hub. This configuration was introduced in QEMU to offer a more advanced emulation alternative to the older I440FX chipset, primarily by incorporating PCI Express (PCIe) support. The "2009" in the name likely indicates the year this specific machine type or its standardization was introduced in QEMU, though the Intel Q35 chipset itself was released in September 2007.

### Specifications

The QEMU "Standard PC (Q35 + ICH9, 2009)" machine type offers the following key specifications and emulated features:

*   **Chipset Architecture:**
    *   **North Bridge:** Emulates the Intel Q35 MCH (Memory Controller Hub).
    *   **South Bridge:** Emulates the Intel ICH9 (I/O Controller Hub).
*   **Bus Architecture:**
    *   **PCI Express (PCIe):** This is a primary advantage over the I440FX, providing a PCIe bus for improved device connectivity and passthrough capabilities.
    *   **PCI Bus:** Also includes a traditional PCI bus.
    *   **LPC Bus:** For SuperIO devices.
    *   **No ISA Bus:** Unlike the older I440FX, the ICH9 natively does not have an ISA bus, simplifying the platform model in QEMU.
*   **Integrated Controllers:**
    *   **AHCI/SATA Controller:** For modern storage devices.
    *   **USB Controller:** Enhanced USB support is provided.
    *   **Network Adapter:** Emulation typically includes common network cards like Intel Gigabit Ethernet (E1000/E1000E) or Realtek 8139C+.
    *   **Audio Adapter:** Integrated audio capabilities.
    *   **SMBus Controller:** Present for system management.
*   **Firmware Support:**
    *   **UEFI Firmware:** Often paired with UEFI firmware like OVMF for modern boot capabilities and features such as Secure Boot. Legacy BIOS is typically not supported by QEMU's Q35 package optimized for UEFI.
*   **Other Features:**
    *   **System Management Mode (SMM):** Industry-standard feature for PC class hardware emulation.
    *   **ACPI Implementation:** Features a more modern ACPI (Advanced Configuration and Power Interface) implementation.
    *   **vIOMMU Emulation:** Supports virtual I/O Memory Management Unit for device assignment (passthrough).
    *   **Clock and Interrupt Controllers:** Includes emulations for RTC (Real-Time Clock), PIT (Programmable Interval Timer), and PICs (Programmable Interrupt Controllers).
*   **Limitations:**
    *   May have questionable support for some legacy QEMU devices.
    *   No support for legacy guests like Windows XP/2000.

### References (URLs)

1.  [Features/Q35 - QEMU](https://wiki.qemu.org/Features/Q35)
2.  [Qemu Q35 Read Me - Project Mu](https://microsoft.github.io/mu/platforms/QemuQ35Pkg/ReadMe/)
3.  [Q35 - Qemu: Marcel Apfelbaum August, 2016 - Scribd](https://www.scribd.com/document/320078235/Q35-Qemu-Marcel-Apfelbaum-August-2016)
4.  [QEMU Standard PC (Q35 + ICH9, 2009) - Geekbench Browser](https://browser.geekbench.com/v4/cpu/14605952)
5.  [QEMU - Machine Platform Emulation - esky916 - 博客园](https://www.cnblogs.com/esky916/p/17926941.html)
6.  [QEMU - Wikipedia](https://en.wikipedia.org/wiki/QEMU#Emulated_hardware_platforms)
7.  [A New Chipset For Qemu - Intel's Q35 Jason Baron - KVM](http://people.redhat.com/~jbaron/q35/QEMU_KVM_Forum_2012.pdf)
8.  [Board: QEMU Standard PC (Q35 + ICH9, 2009) - Model - Pi Benchmarks](https://pibenchmarks.com/board/QEMU_Standard_PC_Q35___ICH9__2009_/)
9.  [docs/q35-chipset.cfg - third_party/qemu - fuchsia Git repositories](https://fuchsia.googlesource.com/third_party/qemu/+/refs/heads/master/docs/q35-chipset.cfg)
10. [QEMU Standard PC (Q35 + ICH9, 2009) - Geekbench](https://browser.geekbench.com/v6/cpu/3890060)
11. [QEMU Standard PC (Q35 + ICH9, 2009) - Geekbench](https://browser.geekbench.com/v5/cpu/21151608)
12. [QEMU Standard PC (Q35 + ICH9, 2009) vs System manufacturer System Product Name - Geekbench](https://browser.geekbench.com/v4/cpu/7926177)
13. [pc+pve0 qemu machine type - what does it mean - Proxmox Support Forum](https://forum.proxmox.com/threads/pc-pve0-qemu-machine-type-what-does-it-mean.141513/)