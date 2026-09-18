<script lang="ts">
    import { Alliance, type EventCoordinates } from "../lib/model";

    interface Props {
        /** Location of the event on the field, in 0..1 coordinates */
        coordinates?: EventCoordinates | null;
        /** Allow the operator to place or move the marker */
        editable?: boolean;
        /** Draw the red alliance on the left, matching the VAR field view */
        swap?: boolean;
        onSetCoordinates?: (coordinates: EventCoordinates) => void;
    }
    let {
        coordinates = null,
        editable = false,
        swap = false,
        onSetCoordinates,
    }: Props = $props();

    // A schematic rather than a scale drawing: enough for an operator to record
    // roughly where on the field something happened.
    let left_alliance = $derived(swap ? Alliance.RED : Alliance.BLUE);
    let right_alliance = $derived(swap ? Alliance.BLUE : Alliance.RED);

    function handleClick(event: MouseEvent) {
        if (!editable) {
            return;
        }
        const target = event.currentTarget as HTMLElement;
        const rect = target.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) {
            return;
        }
        onSetCoordinates?.({
            x: Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1),
            y: Math.min(Math.max((event.clientY - rect.top) / rect.height, 0), 1),
        });
    }
</script>

<button
    class="field-map"
    class:editable
    type="button"
    aria-label={editable ? "Set field location" : "Field location"}
    disabled={!editable}
    onclick={handleClick}
>
    <svg viewBox="0 0 320 160" preserveAspectRatio="none" aria-hidden="true">
        <rect x="0" y="0" width="320" height="160" class="carpet" />
        <rect x="0" y="0" width="70" height="160" class="zone {left_alliance}" />
        <rect x="250" y="0" width="70" height="160" class="zone {right_alliance}" />
        <line x1="160" y1="0" x2="160" y2="160" class="centerline" />
        <circle cx="160" cy="80" r="26" class="hub" />
    </svg>
    {#if coordinates}
        <div
            class="marker"
            style="left: {coordinates.x * 100}%; top: {coordinates.y * 100}%;"
        ></div>
    {/if}
</button>

<style>
    .field-map {
        display: block;
        padding: 0;
        position: relative;
        width: 100%;
        max-width: 420px;
        aspect-ratio: 2 / 1;
        border-radius: 8px;
        overflow: clip;
        box-shadow: 0 0 6px black;
    }

    .field-map.editable {
        cursor: crosshair;
        outline: 2px solid var(--green-action);
        outline-offset: -2px;
    }

    svg {
        width: 100%;
        height: 100%;
        display: block;
    }

    .carpet {
        fill: var(--gray-500);
    }

    .zone.red {
        fill: var(--red-600);
    }

    .zone.blue {
        fill: var(--blue-600);
    }

    .centerline {
        stroke: var(--gray-200);
        stroke-width: 2;
        stroke-dasharray: 6 6;
    }

    .hub {
        fill: none;
        stroke: var(--gray-200);
        stroke-width: 3;
    }

    .marker {
        position: absolute;
        width: 16px;
        height: 16px;
        margin: -8px 0 0 -8px;
        border-radius: 50%;
        background-color: var(--auto-action);
        border: 2px solid black;
        pointer-events: none;
    }
</style>
