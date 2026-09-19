<script lang="ts">
    import { isShiftActive, shiftFuel, shiftLabel, shiftName } from "../lib/game";
    import { Shift, SHIFT_COUNT, type Hub } from "../lib/model";

    interface Props {
        hub: Hub;
        /** Shift currently in progress, highlighted in the strip */
        current_shift?: Shift | null;
    }
    let { hub, current_shift = null }: Props = $props();

    const shifts: Shift[] = Array.from({ length: SHIFT_COUNT }, (_, idx) => idx);

    let cells = $derived(
        shifts.map((shift) => ({
            shift,
            label: shiftLabel(shift),
            name: shiftName(shift),
            active: isShiftActive(hub, shift),
            // Fuel scored while the hub was inactive still gets shown, greyed out, so
            // that the operator can see what the arena discarded.
            count: shiftFuel(hub, shift, false),
        })),
    );
</script>

<div class="shift-strip">
    {#each cells as cell (cell.shift)}
        <div
            class="shift-cell"
            class:inactive={!cell.active}
            class:current={cell.shift === current_shift}
            title="{cell.name}{cell.active ? '' : ' (hub inactive)'}"
        >
            <div class="shift-count">{cell.count}</div>
            <div class="shift-label">{cell.label}</div>
        </div>
    {/each}
</div>

<style>
    .shift-strip {
        display: flex;
        flex-direction: row;
        gap: 2px;
        width: 100%;
    }

    .shift-cell {
        flex: 1 1 0%;
        min-width: 0;
        border-radius: 4px;
        background-color: var(--alliance-action);
        overflow: clip;
        font-variant-numeric: tabular-nums;
    }

    .shift-cell.inactive {
        background-color: var(--neutral-action);
        color: var(--text-inactive-dark);
    }

    .shift-cell.current {
        outline: 2px solid var(--text-active);
        outline-offset: -2px;
    }

    .shift-count {
        font-weight: bold;
        padding: 1px 0;
    }

    .shift-label {
        font-size: 0.7em;
        background-color: #0003;
        padding: 1px 0;
    }
</style>
