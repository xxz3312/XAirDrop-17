# 0123 Version-generator correction and actual target transport

## CRC cause verified in the ICNSS reference

The captured config enables CONFIG_GENDWARFKSYMS. The independent builder omitted the documented stable KABI mode. Enabling KBUILD_GENDWARFKSYMS_STABLE=1 applies the existing unmodified kernel KABI handling and removes all 53 legacy export CRC differences: all 60 old export records, including CRC/license/namespace, match the original ICNSS ELF. The new checked export remains present. Actual provider and ICNSS recorded module checks pass.

The controlled nonstable/stable builds have identical .text, .init.text and .exit.text hashes, and matching mapped pre-entry words in all 60 old exported functions. No kernel type/KABI rule or binary CRC was rewritten. The emitted native rule section contains the existing declonly rule for cgroup_kmi_ext_info; stable mode also applies the generator's existing KABI member handling. This confirms a version-generation mode omission in the reference build, not a need to force original CRCs into the binary.

[Actions 42193275385](https://github.com/xxz3312/XAirDrop-17/actions/runs/42193275385), source 74d52eaed6915ad2bbf3bf4acc345a504447bef4, passed the ICNSS export gate and provider/ICNSS recorded module checks, then rejected the attempted WLAN pairing because the WLAN object did not import the checked ICNSS entry. The compact and binary artifact digests, all 18 actual compiler/type/config files and rule-section digest were verified. See [mode validation](research/popsicle-crc-mode-0123-validation.json).

## Actual target correction

The original stock qca_cld3_peach_v2.ko imports cnss_wlan_register_driver and cnss_wlan_unregister_driver, has no ICNSS registration imports, and depends on cnss2. The pinned canoe_gki_peach-v2_defconfig enables CONFIG_PLD_PCIE_CNSS_FLAG and CONFIG_PLD_PCIE_INIT_FLAG without CONFIG_PLD_IPCI_ICNSS_FLAG. The actual target is PCIe/CNSS2. Treating ICNSS as its main entry path was incorrect.

Stages 0118–0122 validated IPCI-specific source/model behavior, not this target's native entry path. Generic host/runtime changes remain available but are not automatically certified for PCIe. No target WLAN pair or phone activation has been completed by the ICNSS work.

A new source-profile/actual-stock-import transport audit rejects ambiguous selection, changed profiles, mismatched imports and incorrect labels. The stock evidence records original ELF/archive hashes and dependency/import lists. Four new meaningful rejection regressions bring Python checks to 57. The strict pair builder refuses a wrong target bus before WLAN compilation. ICNSS is retained only as an explicitly requested reference-only build; default CI no longer runs it as a mandatory target pair. Reference-only success is labeled ICNSS_REFERENCE_LINK_AND_RECORDED_CHECKS_ONLY and leaves paired_WLAN_built false.

The next target implementation must connect pld_pcie.c and platform/cnss2/pci.c with the actual PCIe callback signatures and CNSS2 unregister lifecycle. Forcing IPCI configuration is not an adaptation. See [transport evidence](research/popsicle-target-transport-0123.json) and [pinned original transport](../kernel/abi/popsicle-stock-transport.json).

## Diagnostic boundaries

The earlier bounded transitive stock BTF/candidate DWARF comparison visited 2,858 type pairs with 196 incomplete paths; the expanded qualified view visited 2,974 with the same incomplete paths. These were narrowing diagnostics, not ABI proof. A short-commit lookup in official kernel/common resolves the candidate control prefix but returns 404 for the stock 43b5ab7e247d prefix; that single-origin check does not establish global source unavailability.

[Kernel documentation](https://android.googlesource.com/kernel/common/+/e2b8ca7c8d0551a6124b1a7322f5ae532845f1b5/Documentation/kbuild/gendwarfksyms.rst) describes KBUILD_GENDWARFKSYMS_STABLE. [android_kabi.h](https://android.googlesource.com/kernel/common/+/e2b8ca7c8d0551a6124b1a7322f5ae532845f1b5/include/linux/android_kabi.h) supplies the existing annotations; this project adds none.

No complete private layout/KCFI, platform replacement, module-exit failure, radio backend, Apple discovery/handshake or file-transfer certification follows from this reference CRC fix. No phone operation occurred.
