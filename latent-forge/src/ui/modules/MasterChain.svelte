<script lang="ts">
  // M1 FRAME ONLY. Spec §4.6.5's LATCH HEAD toggle + head select, GAIN (0-120,
  // default 64) and LATENT NORMALISE (default on) are M7. Do not build them here.
</script>

<p class="note">applied to the mixed latent, after the lane chains</p>
<p class="pending">LATCH HEAD, GAIN and LATENT NORMALISE arrive in M7</p>

<style>
  .note,
  .pending {
    margin: 0;
    padding: 4px 10px;
    font-size: 10px;
    line-height: 1.45;
    color: var(--text-dim);
  }
  .pending {
    padding-bottom: 8px;
  }
</style>
