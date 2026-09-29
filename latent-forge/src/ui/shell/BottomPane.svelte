<script lang="ts">
  // Spec §4.1/§4.5. The three boxes are empty here; Task 11 fills them with the
  // tab row, the four tab bodies and the render preview container frame.
  //
  // Height budget, asserted by the layout test:
  //   248 − 1 (border-top) − 6 (padding-top) − 8 (padding-bottom) = 233
  //   233 − 162 (tab body) − 44 (preview container)               = 27 (tab row)
  interface Props {
    visible?: boolean;
  }
  let { visible = true }: Props = $props();
</script>

<div class="bottom-pane" class:hidden={!visible} data-region="bottom-pane">
  <div class="tab-row" data-region="bottom-tab-row"></div>
  <div class="tab-body" data-region="bottom-tab-body"></div>
  <div class="preview-slot" data-region="preview-slot"></div>
</div>

<style>
  .bottom-pane {
    box-sizing: border-box;
    flex-shrink: 0;
    height: 248px;
    padding: 6px 10px 8px;
    background: var(--bg);
    border-top: 1px solid var(--border);
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .bottom-pane.hidden {
    display: none;
  }
  .tab-row {
    box-sizing: border-box;
    flex: 0 0 27px;
    display: flex;
    align-items: center;
    gap: 3px;
    padding-bottom: 5px;
  }
  .tab-body {
    box-sizing: border-box;
    flex: 0 0 162px;
    min-height: 0;
    overflow: hidden;
  }
  .preview-slot {
    box-sizing: border-box;
    flex: 0 0 44px;
  }
</style>
