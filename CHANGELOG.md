# Changelog

## [v0.6.0](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.6.0) (2024-01-24)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/v0.5.7...v0.6.0)

**Implemented enhancements:**

- feat: update Autofocus related methods, warn when 'Set AF Offset per Position' checked but autofocus not engaged [\#262](https://github.com/pymmcore-plus/pymmcore-widgets/pull/262) ([fdrgsp](https://github.com/fdrgsp))
- feat: add the possibility to invert the axis in the stage widget [\#260](https://github.com/pymmcore-plus/pymmcore-widgets/pull/260) ([fdrgsp](https://github.com/fdrgsp))
- feat: PixelConfigurationWidget with similar logic as in micromanager [\#244](https://github.com/pymmcore-plus/pymmcore-widgets/pull/244) ([fdrgsp](https://github.com/fdrgsp))

**Fixed bugs:**

- fix: fix missing hub peripherals in config wizard [\#264](https://github.com/pymmcore-plus/pymmcore-widgets/pull/264) ([tlambert03](https://github.com/tlambert03))
- fix: hide invert xy checkboxes if not xy stage in StageWidget [\#261](https://github.com/pymmcore-plus/pymmcore-widgets/pull/261) ([fdrgsp](https://github.com/fdrgsp))

**Merged pull requests:**

- ci\(pre-commit.ci\): autoupdate [\#258](https://github.com/pymmcore-plus/pymmcore-widgets/pull/258) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- docs: update the docs [\#255](https://github.com/pymmcore-plus/pymmcore-widgets/pull/255) ([fdrgsp](https://github.com/fdrgsp))

## [v0.5.7](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.5.7) (2023-12-19)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/v0.5.6...v0.5.7)

**Fixed bugs:**

- fix: fix quantity edit [\#257](https://github.com/pymmcore-plus/pymmcore-widgets/pull/257) ([tlambert03](https://github.com/tlambert03))

**Merged pull requests:**

- ci\(dependabot\): bump actions/setup-python from 4 to 5 [\#254](https://github.com/pymmcore-plus/pymmcore-widgets/pull/254) ([dependabot[bot]](https://github.com/apps/dependabot))
- ci\(pre-commit.ci\): autoupdate [\#252](https://github.com/pymmcore-plus/pymmcore-widgets/pull/252) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- test: fix tests for pymmcore 11.1.1.71.0 [\#251](https://github.com/pymmcore-plus/pymmcore-widgets/pull/251) ([tlambert03](https://github.com/tlambert03))
- fix: fix overlap in GridPlanWidget [\#249](https://github.com/pymmcore-plus/pymmcore-widgets/pull/249) ([fdrgsp](https://github.com/fdrgsp))
- fix: minor fix in save config in GroupPresetTableWidget [\#248](https://github.com/pymmcore-plus/pymmcore-widgets/pull/248) ([fdrgsp](https://github.com/fdrgsp))
- feat: expose new useq\_widgets and core-connected MDAWidget and update the docs [\#247](https://github.com/pymmcore-plus/pymmcore-widgets/pull/247) ([fdrgsp](https://github.com/fdrgsp))
- ci\(pre-commit.ci\): autoupdate [\#243](https://github.com/pymmcore-plus/pymmcore-widgets/pull/243) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- fix: fix the test on PyQt6 [\#242](https://github.com/pymmcore-plus/pymmcore-widgets/pull/242) ([fdrgsp](https://github.com/fdrgsp))
- fix: fix style of ZPlanWidget [\#239](https://github.com/pymmcore-plus/pymmcore-widgets/pull/239) ([fdrgsp](https://github.com/fdrgsp))
- feat: update keep\_shutter\_open and autofocus axis checkboxes [\#231](https://github.com/pymmcore-plus/pymmcore-widgets/pull/231) ([fdrgsp](https://github.com/fdrgsp))

## [v0.5.6](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.5.6) (2023-11-01)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/v0.5.5...v0.5.6)

**Merged pull requests:**

- feat: add step\(\) and setStep\(\) methods to StageWidget [\#241](https://github.com/pymmcore-plus/pymmcore-widgets/pull/241) ([tlambert03](https://github.com/tlambert03))
- docs: fix docs build [\#237](https://github.com/pymmcore-plus/pymmcore-widgets/pull/237) ([tlambert03](https://github.com/tlambert03))
- feat: add installation manager [\#236](https://github.com/pymmcore-plus/pymmcore-widgets/pull/236) ([tlambert03](https://github.com/tlambert03))

## [v0.5.5](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.5.5) (2023-10-24)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/v0.5.4...v0.5.5)

**Merged pull requests:**

- fix: disallow setting pre-init props after device initialization [\#234](https://github.com/pymmcore-plus/pymmcore-widgets/pull/234) ([tlambert03](https://github.com/tlambert03))
- fix: hide shutter open in sub\_seq [\#229](https://github.com/pymmcore-plus/pymmcore-widgets/pull/229) ([fdrgsp](https://github.com/fdrgsp))

## [v0.5.4](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.5.4) (2023-10-12)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/v0.5.3...v0.5.4)

**Merged pull requests:**

- feat: add back the autofocus logic to the PositionTable [\#201](https://github.com/pymmcore-plus/pymmcore-widgets/pull/201) ([fdrgsp](https://github.com/fdrgsp))

## [v0.5.3](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.5.3) (2023-10-12)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/v0.5.2...v0.5.3)

**Merged pull requests:**

- fix: fix exposure on mda range [\#225](https://github.com/pymmcore-plus/pymmcore-widgets/pull/225) ([tlambert03](https://github.com/tlambert03))

## [v0.5.2](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.5.2) (2023-10-12)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/v0.5.1...v0.5.2)

**Merged pull requests:**

- fix: catch errors in property widget when building device property table [\#224](https://github.com/pymmcore-plus/pymmcore-widgets/pull/224) ([tlambert03](https://github.com/tlambert03))
- fix: extend exposure widget range [\#222](https://github.com/pymmcore-plus/pymmcore-widgets/pull/222) ([tlambert03](https://github.com/tlambert03))

## [v0.5.1](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.5.1) (2023-10-09)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/v0.5.0...v0.5.1)

**Fixed bugs:**

- fix: fix correct index enablement on checkable tab widget [\#206](https://github.com/pymmcore-plus/pymmcore-widgets/pull/206) ([tlambert03](https://github.com/tlambert03))

**Merged pull requests:**

- fix: fix new mdaexample without channels [\#221](https://github.com/pymmcore-plus/pymmcore-widgets/pull/221) ([tlambert03](https://github.com/tlambert03))
- fix: retain pointers in QCheckableTabWidget [\#220](https://github.com/pymmcore-plus/pymmcore-widgets/pull/220) ([tlambert03](https://github.com/tlambert03))
- fix: accept 0 as interval [\#219](https://github.com/pymmcore-plus/pymmcore-widgets/pull/219) ([fdrgsp](https://github.com/fdrgsp))
- ci\(pre-commit.ci\): autoupdate [\#218](https://github.com/pymmcore-plus/pymmcore-widgets/pull/218) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- fix: fix pre-commit [\#217](https://github.com/pymmcore-plus/pymmcore-widgets/pull/217) ([fdrgsp](https://github.com/fdrgsp))
- fix: units to µm [\#215](https://github.com/pymmcore-plus/pymmcore-widgets/pull/215) ([fdrgsp](https://github.com/fdrgsp))
- fix: add position if relative z\_plan [\#213](https://github.com/pymmcore-plus/pymmcore-widgets/pull/213) ([fdrgsp](https://github.com/fdrgsp))
- fix: fix icon transform [\#212](https://github.com/pymmcore-plus/pymmcore-widgets/pull/212) ([fdrgsp](https://github.com/fdrgsp))
- fix: use core connected widgets for core connected  sub-sequence \_MDAPopup [\#211](https://github.com/pymmcore-plus/pymmcore-widgets/pull/211) ([fdrgsp](https://github.com/fdrgsp))
- fix: increase FloatColumn min/max in Position table [\#209](https://github.com/pymmcore-plus/pymmcore-widgets/pull/209) ([fdrgsp](https://github.com/fdrgsp))
- fix: update CoreConnectedPositionTable + test [\#208](https://github.com/pymmcore-plus/pymmcore-widgets/pull/208) ([fdrgsp](https://github.com/fdrgsp))
- test: don't emit sequenceStarted explicitly in tests [\#207](https://github.com/pymmcore-plus/pymmcore-widgets/pull/207) ([tlambert03](https://github.com/tlambert03))

## [v0.5.0](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.5.0) (2023-09-23)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/v0.4.2...v0.5.0)

**Merged pull requests:**

- fix: treat MDASequence.axis\_order as Sequence\[str\] rather than str [\#204](https://github.com/pymmcore-plus/pymmcore-widgets/pull/204) ([tlambert03](https://github.com/tlambert03))
- fix: don't set Null MDASequence values in position table, cast dicts to MDASequence in MDAButton.setValue [\#203](https://github.com/pymmcore-plus/pymmcore-widgets/pull/203) ([fdrgsp](https://github.com/fdrgsp))
- refactor: remove icon svgs [\#202](https://github.com/pymmcore-plus/pymmcore-widgets/pull/202) ([tlambert03](https://github.com/tlambert03))
- fix: remove grid paint + fix grid units for GridWidthHeight [\#200](https://github.com/pymmcore-plus/pymmcore-widgets/pull/200) ([fdrgsp](https://github.com/fdrgsp))
- feat: valueChanged to \_SaveGroupBox [\#199](https://github.com/pymmcore-plus/pymmcore-widgets/pull/199) ([fdrgsp](https://github.com/fdrgsp))
- fix: fix objective widget resizing [\#196](https://github.com/pymmcore-plus/pymmcore-widgets/pull/196) ([fdrgsp](https://github.com/fdrgsp))
- ci\(dependabot\): bump actions/checkout from 3 to 4 [\#194](https://github.com/pymmcore-plus/pymmcore-widgets/pull/194) ([dependabot[bot]](https://github.com/apps/dependabot))
- ci\(pre-commit.ci\): autoupdate [\#193](https://github.com/pymmcore-plus/pymmcore-widgets/pull/193) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- feat: runnable, core-connected mda widget, based on new useq widgets [\#192](https://github.com/pymmcore-plus/pymmcore-widgets/pull/192) ([tlambert03](https://github.com/tlambert03))
- test: try fix tests by relaxing windows leak tests [\#190](https://github.com/pymmcore-plus/pymmcore-widgets/pull/190) ([tlambert03](https://github.com/tlambert03))
- docs: Update README.md [\#189](https://github.com/pymmcore-plus/pymmcore-widgets/pull/189) ([tlambert03](https://github.com/tlambert03))
- feat: add configuration wizard [\#183](https://github.com/pymmcore-plus/pymmcore-widgets/pull/183) ([tlambert03](https://github.com/tlambert03))
- feat: new useq-schema widgets [\#180](https://github.com/pymmcore-plus/pymmcore-widgets/pull/180) ([tlambert03](https://github.com/tlambert03))

## [v0.4.2](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.4.2) (2023-09-01)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/v0.4.1...v0.4.2)

**Merged pull requests:**

- fix: fix napari micro tests [\#188](https://github.com/pymmcore-plus/pymmcore-widgets/pull/188) ([tlambert03](https://github.com/tlambert03))
- fix: fix pre-commit [\#186](https://github.com/pymmcore-plus/pymmcore-widgets/pull/186) ([tlambert03](https://github.com/tlambert03))
- fix: remove groupbox from config widget [\#185](https://github.com/pymmcore-plus/pymmcore-widgets/pull/185) ([fdrgsp](https://github.com/fdrgsp))
- ci\(pre-commit.ci\): autoupdate [\#182](https://github.com/pymmcore-plus/pymmcore-widgets/pull/182) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))

## [v0.4.1](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.4.1) (2023-08-01)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/v0.4.0...v0.4.1)

**Merged pull requests:**

- build: updates for fov\_size in useq 0.4, bump pymmcore-plus [\#175](https://github.com/pymmcore-plus/pymmcore-widgets/pull/175) ([tlambert03](https://github.com/tlambert03))
- fix: catch errors when updating property browser values from core [\#174](https://github.com/pymmcore-plus/pymmcore-widgets/pull/174) ([tlambert03](https://github.com/tlambert03))
- refactor: return useq object from stack\_widget.value\(\) [\#173](https://github.com/pymmcore-plus/pymmcore-widgets/pull/173) ([tlambert03](https://github.com/tlambert03))
- refactor: use useq-schema objects for GridWidget [\#171](https://github.com/pymmcore-plus/pymmcore-widgets/pull/171) ([tlambert03](https://github.com/tlambert03))
- refactor: use useq.Channel objects in `ChannelTable` [\#170](https://github.com/pymmcore-plus/pymmcore-widgets/pull/170) ([tlambert03](https://github.com/tlambert03))
- fix: remove set\_state core link  in PositionTable [\#169](https://github.com/pymmcore-plus/pymmcore-widgets/pull/169) ([fdrgsp](https://github.com/fdrgsp))
- refactor: remove time estimates from MDAWidget [\#168](https://github.com/pymmcore-plus/pymmcore-widgets/pull/168) ([tlambert03](https://github.com/tlambert03))
- test: update grid tests to work with old and new useq-grid plan [\#166](https://github.com/pymmcore-plus/pymmcore-widgets/pull/166) ([tlambert03](https://github.com/tlambert03))
- chore: miscellaneous updates, update linting rules [\#161](https://github.com/pymmcore-plus/pymmcore-widgets/pull/161) ([tlambert03](https://github.com/tlambert03))

## [v0.4.0](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.4.0) (2023-07-27)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/v0.3.0...v0.4.0)

**Fixed bugs:**

- fix: reduce widget freezing [\#154](https://github.com/pymmcore-plus/pymmcore-widgets/pull/154) ([wl-stepp](https://github.com/wl-stepp))

**Merged pull requests:**

- refactor: make SaveLoadSequenceWidget private [\#160](https://github.com/pymmcore-plus/pymmcore-widgets/pull/160) ([fdrgsp](https://github.com/fdrgsp))
- fix: don't calculate time before subclasses have been inited [\#159](https://github.com/pymmcore-plus/pymmcore-widgets/pull/159) ([ianhi](https://github.com/ianhi))
- perf: Improve speed of mda widget [\#157](https://github.com/pymmcore-plus/pymmcore-widgets/pull/157) ([ianhi](https://github.com/ianhi))
- test: add test for core state modification [\#155](https://github.com/pymmcore-plus/pymmcore-widgets/pull/155) ([tlambert03](https://github.com/tlambert03))
- fix: minor time widget fix [\#153](https://github.com/pymmcore-plus/pymmcore-widgets/pull/153) ([fdrgsp](https://github.com/fdrgsp))
- fix: remove useq NoX plans [\#152](https://github.com/pymmcore-plus/pymmcore-widgets/pull/152) ([fdrgsp](https://github.com/fdrgsp))
- chore: update pre-commit [\#148](https://github.com/pymmcore-plus/pymmcore-widgets/pull/148) ([tlambert03](https://github.com/tlambert03))
- feat: add micromanager autofocus device control autofocus [\#147](https://github.com/pymmcore-plus/pymmcore-widgets/pull/147) ([fdrgsp](https://github.com/fdrgsp))
- feat: save and load MDASequence [\#146](https://github.com/pymmcore-plus/pymmcore-widgets/pull/146) ([fdrgsp](https://github.com/fdrgsp))
- fix: update ShutterWidget for new snapImage signals + tests [\#145](https://github.com/pymmcore-plus/pymmcore-widgets/pull/145) ([fdrgsp](https://github.com/fdrgsp))
- fix: remove redundant 'removeRow\(row\)'  [\#143](https://github.com/pymmcore-plus/pymmcore-widgets/pull/143) ([fdrgsp](https://github.com/fdrgsp))
- ci\(pre-commit.ci\): autoupdate [\#141](https://github.com/pymmcore-plus/pymmcore-widgets/pull/141) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- feat: mda in a QTabWidget [\#140](https://github.com/pymmcore-plus/pymmcore-widgets/pull/140) ([fdrgsp](https://github.com/fdrgsp))
- fix: Remove QGroupBox from ChannelTable, ZStackWidget, PositionTable,  and TimePlanWidget [\#139](https://github.com/pymmcore-plus/pymmcore-widgets/pull/139) ([fdrgsp](https://github.com/fdrgsp))
- ci: update pre-commit [\#138](https://github.com/pymmcore-plus/pymmcore-widgets/pull/138) ([tlambert03](https://github.com/tlambert03))
- ci\(pre-commit.ci\): autoupdate [\#137](https://github.com/pymmcore-plus/pymmcore-widgets/pull/137) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- fix: minor fix in PresetsWidget [\#136](https://github.com/pymmcore-plus/pymmcore-widgets/pull/136) ([fdrgsp](https://github.com/fdrgsp))
- feat: add AutoRepeat to stage buttons [\#135](https://github.com/pymmcore-plus/pymmcore-widgets/pull/135) ([fdrgsp](https://github.com/fdrgsp))
- ci\(pre-commit.ci\): autoupdate [\#134](https://github.com/pymmcore-plus/pymmcore-widgets/pull/134) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- feat: add phases to TimePlanWidget [\#132](https://github.com/pymmcore-plus/pymmcore-widgets/pull/132) ([fdrgsp](https://github.com/fdrgsp))
- feat: add channel advanced warning icon [\#130](https://github.com/pymmcore-plus/pymmcore-widgets/pull/130) ([fdrgsp](https://github.com/fdrgsp))
- feat: add "advanced" channel options to ChannelTable [\#129](https://github.com/pymmcore-plus/pymmcore-widgets/pull/129) ([fdrgsp](https://github.com/fdrgsp))
- ci\(pre-commit.ci\): autoupdate [\#127](https://github.com/pymmcore-plus/pymmcore-widgets/pull/127) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- feat: update GridWidget and PositionTable widget [\#126](https://github.com/pymmcore-plus/pymmcore-widgets/pull/126) ([fdrgsp](https://github.com/fdrgsp))
- ci\(pre-commit.ci\): autoupdate [\#123](https://github.com/pymmcore-plus/pymmcore-widgets/pull/123) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- fix: Stop shutter widget from accidentally closing shutter [\#121](https://github.com/pymmcore-plus/pymmcore-widgets/pull/121) ([ianhi](https://github.com/ianhi))
- feat: updated version of Channel Table Widget [\#113](https://github.com/pymmcore-plus/pymmcore-widgets/pull/113) ([fdrgsp](https://github.com/fdrgsp))
- test: add napari-micromanager test [\#103](https://github.com/pymmcore-plus/pymmcore-widgets/pull/103) ([tlambert03](https://github.com/tlambert03))

## [v0.3.0](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.3.0) (2023-01-14)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/v0.2.1...v0.3.0)

**Merged pull requests:**

- docs: add time and z plan widgets to docs [\#120](https://github.com/pymmcore-plus/pymmcore-widgets/pull/120) ([fdrgsp](https://github.com/fdrgsp))
- refactor: extract basic position table [\#119](https://github.com/pymmcore-plus/pymmcore-widgets/pull/119) ([fdrgsp](https://github.com/fdrgsp))
- fix: fix docs build [\#117](https://github.com/pymmcore-plus/pymmcore-widgets/pull/117) ([tlambert03](https://github.com/tlambert03))
- fix: fix for pre Test and utilities state device shutter [\#116](https://github.com/pymmcore-plus/pymmcore-widgets/pull/116) ([fdrgsp](https://github.com/fdrgsp))
- ci\(pre-commit.ci\): autoupdate [\#115](https://github.com/pymmcore-plus/pymmcore-widgets/pull/115) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- fix: fix MDA run\_button not showing when \_include\_run\_button=True [\#111](https://github.com/pymmcore-plus/pymmcore-widgets/pull/111) ([fdrgsp](https://github.com/fdrgsp))
- fix: fix typing in sample explorer [\#110](https://github.com/pymmcore-plus/pymmcore-widgets/pull/110) ([tlambert03](https://github.com/tlambert03))
- refactor: make \_GridParams class for \_create\_row\_cols\_overlap\_group [\#107](https://github.com/pymmcore-plus/pymmcore-widgets/pull/107) ([tlambert03](https://github.com/tlambert03))
- fix: subclass explorer from mda [\#106](https://github.com/pymmcore-plus/pymmcore-widgets/pull/106) ([fdrgsp](https://github.com/fdrgsp))
- refactor: remove sliderwidget [\#104](https://github.com/pymmcore-plus/pymmcore-widgets/pull/104) ([tlambert03](https://github.com/tlambert03))
- refactor: move mda components [\#102](https://github.com/pymmcore-plus/pymmcore-widgets/pull/102) ([tlambert03](https://github.com/tlambert03))
- refactor: extract duplicated Channel Table code between mda and sample explorer [\#100](https://github.com/pymmcore-plus/pymmcore-widgets/pull/100) ([fdrgsp](https://github.com/fdrgsp))
- docs: add favicon [\#99](https://github.com/pymmcore-plus/pymmcore-widgets/pull/99) ([ianhi](https://github.com/ianhi))
- fix: fix bug in channel widget  [\#98](https://github.com/pymmcore-plus/pymmcore-widgets/pull/98) ([fdrgsp](https://github.com/fdrgsp))
- fix: remove print statement [\#97](https://github.com/pymmcore-plus/pymmcore-widgets/pull/97) ([tlambert03](https://github.com/tlambert03))
- fix: change property browser icons color to gray [\#96](https://github.com/pymmcore-plus/pymmcore-widgets/pull/96) ([fdrgsp](https://github.com/fdrgsp))
- refactor: extract duplicated TimePlan widget code between mda and sample explorer [\#94](https://github.com/pymmcore-plus/pymmcore-widgets/pull/94) ([tlambert03](https://github.com/tlambert03))

## [v0.2.1](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.2.1) (2022-12-05)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/v0.2.0...v0.2.1)

**Merged pull requests:**

- build: bump core dep [\#92](https://github.com/pymmcore-plus/pymmcore-widgets/pull/92) ([tlambert03](https://github.com/tlambert03))
- feat: PropertiesWidget [\#90](https://github.com/pymmcore-plus/pymmcore-widgets/pull/90) ([tlambert03](https://github.com/tlambert03))

## [v0.2.0](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.2.0) (2022-12-03)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/v0.1.1...v0.2.0)

**Merged pull requests:**

- Update README.md docs [\#89](https://github.com/pymmcore-plus/pymmcore-widgets/pull/89) ([tlambert03](https://github.com/tlambert03))
- fix: minor fixes for PropertyBrowser and DeviceTypeFilters [\#88](https://github.com/pymmcore-plus/pymmcore-widgets/pull/88) ([fdrgsp](https://github.com/fdrgsp))
- style: Prettify typing optional [\#87](https://github.com/pymmcore-plus/pymmcore-widgets/pull/87) ([tlambert03](https://github.com/tlambert03))
- feat: allow propertywidget to disconnect from core [\#86](https://github.com/pymmcore-plus/pymmcore-widgets/pull/86) ([tlambert03](https://github.com/tlambert03))
- test: fix windows segfaults on image test [\#85](https://github.com/pymmcore-plus/pymmcore-widgets/pull/85) ([tlambert03](https://github.com/tlambert03))
- refactor: factor out `DevicePropertyTable` from PropBrowser, AddGroup, and EditGroup widgets [\#84](https://github.com/pymmcore-plus/pymmcore-widgets/pull/84) ([tlambert03](https://github.com/tlambert03))
- refactor: extract duplicated device filter widget code [\#83](https://github.com/pymmcore-plus/pymmcore-widgets/pull/83) ([tlambert03](https://github.com/tlambert03))
- test: fix and assert widget cleanup [\#82](https://github.com/pymmcore-plus/pymmcore-widgets/pull/82) ([tlambert03](https://github.com/tlambert03))
- test: cleanup grid widget after test [\#81](https://github.com/pymmcore-plus/pymmcore-widgets/pull/81) ([tlambert03](https://github.com/tlambert03))
- fix: disable z checkbox at startup [\#80](https://github.com/pymmcore-plus/pymmcore-widgets/pull/80) ([fdrgsp](https://github.com/fdrgsp))
- refactor: cleanup z tab selector [\#79](https://github.com/pymmcore-plus/pymmcore-widgets/pull/79) ([tlambert03](https://github.com/tlambert03))
- feat: General Widgets for MDAs [\#78](https://github.com/pymmcore-plus/pymmcore-widgets/pull/78) ([fdrgsp](https://github.com/fdrgsp))
- refactor: cleanup some types on mda and sample widgets [\#75](https://github.com/pymmcore-plus/pymmcore-widgets/pull/75) ([tlambert03](https://github.com/tlambert03))
- style: use ruff [\#74](https://github.com/pymmcore-plus/pymmcore-widgets/pull/74) ([tlambert03](https://github.com/tlambert03))

## [v0.1.1](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.1.1) (2022-11-24)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/v0.1.0...v0.1.1)

**Implemented enhancements:**

- feat: add pixel size widget [\#25](https://github.com/pymmcore-plus/pymmcore-widgets/pull/25) ([fdrgsp](https://github.com/fdrgsp))

**Merged pull requests:**

- ci: add ci to build docs [\#73](https://github.com/pymmcore-plus/pymmcore-widgets/pull/73) ([tlambert03](https://github.com/tlambert03))
- refactor: correct many Qt namespaces [\#72](https://github.com/pymmcore-plus/pymmcore-widgets/pull/72) ([tlambert03](https://github.com/tlambert03))
- fix: remove \_update\_mda\_engine and correct pyside6 enums [\#71](https://github.com/pymmcore-plus/pymmcore-widgets/pull/71) ([fdrgsp](https://github.com/fdrgsp))
- fix: core -\> mmcore [\#70](https://github.com/pymmcore-plus/pymmcore-widgets/pull/70) ([fdrgsp](https://github.com/fdrgsp))
- fix: fix sequence acquisition signal names [\#69](https://github.com/pymmcore-plus/pymmcore-widgets/pull/69) ([fdrgsp](https://github.com/fdrgsp))
- fix: use standard StateDeviceWidget if no FocusDevice [\#68](https://github.com/pymmcore-plus/pymmcore-widgets/pull/68) ([fdrgsp](https://github.com/fdrgsp))
- fix: unpin micromanager from pre-test [\#67](https://github.com/pymmcore-plus/pymmcore-widgets/pull/67) ([fdrgsp](https://github.com/fdrgsp))
- test: unpin mm device version [\#66](https://github.com/pymmcore-plus/pymmcore-widgets/pull/66) ([tlambert03](https://github.com/tlambert03))
- ci: \[pre-commit.ci\] autoupdate [\#65](https://github.com/pymmcore-plus/pymmcore-widgets/pull/65) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- docs: Add Examples [\#63](https://github.com/pymmcore-plus/pymmcore-widgets/pull/63) ([fdrgsp](https://github.com/fdrgsp))
- docs: add docs using mkdocs [\#62](https://github.com/pymmcore-plus/pymmcore-widgets/pull/62) ([fdrgsp](https://github.com/fdrgsp))
- ci\(dependabot\): bump styfle/cancel-workflow-action from 0.10.1 to 0.11.0 [\#61](https://github.com/pymmcore-plus/pymmcore-widgets/pull/61) ([dependabot[bot]](https://github.com/apps/dependabot))
- test: Fix pre-test [\#60](https://github.com/pymmcore-plus/pymmcore-widgets/pull/60) ([fdrgsp](https://github.com/fdrgsp))
- fix: add vispy to pyproject.toml test [\#58](https://github.com/pymmcore-plus/pymmcore-widgets/pull/58) ([fdrgsp](https://github.com/fdrgsp))
- ci\(dependabot\): bump styfle/cancel-workflow-action from 0.10.0 to 0.10.1 [\#55](https://github.com/pymmcore-plus/pymmcore-widgets/pull/55) ([dependabot[bot]](https://github.com/apps/dependabot))
- ci: \[pre-commit.ci\] autoupdate [\#54](https://github.com/pymmcore-plus/pymmcore-widgets/pull/54) ([pre-commit-ci[bot]](https://github.com/apps/pre-commit-ci))
- chore: Update precommit [\#53](https://github.com/pymmcore-plus/pymmcore-widgets/pull/53) ([tlambert03](https://github.com/tlambert03))
- feat: add Sample Explorer widget [\#51](https://github.com/pymmcore-plus/pymmcore-widgets/pull/51) ([fdrgsp](https://github.com/fdrgsp))
- fix: fix state error in snap and live buttons [\#50](https://github.com/pymmcore-plus/pymmcore-widgets/pull/50) ([tlambert03](https://github.com/tlambert03))
- feat: image widget [\#49](https://github.com/pymmcore-plus/pymmcore-widgets/pull/49) ([tlambert03](https://github.com/tlambert03))
- feat: update GroupPresetTableWidget + PresetsWidget + tests [\#48](https://github.com/pymmcore-plus/pymmcore-widgets/pull/48) ([fdrgsp](https://github.com/fdrgsp))
- feat: Add Camera ROI widget + test [\#47](https://github.com/pymmcore-plus/pymmcore-widgets/pull/47) ([fdrgsp](https://github.com/fdrgsp))
- docs: update readme badges [\#46](https://github.com/pymmcore-plus/pymmcore-widgets/pull/46) ([tlambert03](https://github.com/tlambert03))
- fix: move LIVE button \_\_init\_\_ args to properties + update test [\#31](https://github.com/pymmcore-plus/pymmcore-widgets/pull/31) ([fdrgsp](https://github.com/fdrgsp))
- feat: add MultiD widget [\#26](https://github.com/pymmcore-plus/pymmcore-widgets/pull/26) ([fdrgsp](https://github.com/fdrgsp))
- feat: add Shutter widget [\#24](https://github.com/pymmcore-plus/pymmcore-widgets/pull/24) ([fdrgsp](https://github.com/fdrgsp))

## [v0.1.0](https://github.com/pymmcore-plus/pymmcore-widgets/tree/v0.1.0) (2022-08-01)

[Full Changelog](https://github.com/pymmcore-plus/pymmcore-widgets/compare/6362bd285c667204a9ce05b0d52595fde1dc7cbc...v0.1.0)

**Merged pull requests:**

- docs: Update README.md [\#45](https://github.com/pymmcore-plus/pymmcore-widgets/pull/45) ([tlambert03](https://github.com/tlambert03))
- docs: Update README.md [\#44](https://github.com/pymmcore-plus/pymmcore-widgets/pull/44) ([tlambert03](https://github.com/tlambert03))
- ci: fix token secret name [\#43](https://github.com/pymmcore-plus/pymmcore-widgets/pull/43) ([tlambert03](https://github.com/tlambert03))
- Fix: Remove 'get\_core\_singleton\(\)' and replace with CMMCorePlus.instance\(\) [\#41](https://github.com/pymmcore-plus/pymmcore-widgets/pull/41) ([fdrgsp](https://github.com/fdrgsp))
- fix: fix \_set\_combo\_view method [\#40](https://github.com/pymmcore-plus/pymmcore-widgets/pull/40) ([fdrgsp](https://github.com/fdrgsp))
- remove style args from SNAP button \_\_init\_\_  + update test [\#39](https://github.com/pymmcore-plus/pymmcore-widgets/pull/39) ([fdrgsp](https://github.com/fdrgsp))
- fix: fix pre-tests [\#38](https://github.com/pymmcore-plus/pymmcore-widgets/pull/38) ([ianhi](https://github.com/ianhi))
- fix: fix pre-tests [\#34](https://github.com/pymmcore-plus/pymmcore-widgets/pull/34) ([ianhi](https://github.com/ianhi))
- fix: fix pre tests [\#29](https://github.com/pymmcore-plus/pymmcore-widgets/pull/29) ([tlambert03](https://github.com/tlambert03))
- feat: add Load System cfg widget [\#23](https://github.com/pymmcore-plus/pymmcore-widgets/pull/23) ([fdrgsp](https://github.com/fdrgsp))
- feat: add Slider Dialog widget [\#22](https://github.com/pymmcore-plus/pymmcore-widgets/pull/22) ([fdrgsp](https://github.com/fdrgsp))
- feat: add Objectives widget [\#21](https://github.com/pymmcore-plus/pymmcore-widgets/pull/21) ([fdrgsp](https://github.com/fdrgsp))
- feat: add Channel widget [\#20](https://github.com/pymmcore-plus/pymmcore-widgets/pull/20) ([fdrgsp](https://github.com/fdrgsp))
- add Group and Preset widget [\#19](https://github.com/pymmcore-plus/pymmcore-widgets/pull/19) ([fdrgsp](https://github.com/fdrgsp))
- test: Fix github tests [\#18](https://github.com/pymmcore-plus/pymmcore-widgets/pull/18) ([tlambert03](https://github.com/tlambert03))



\* *This Changelog was automatically generated by [github_changelog_generator](https://github.com/github-changelog-generator/github-changelog-generator)*
