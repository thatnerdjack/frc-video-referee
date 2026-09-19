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
    const FIELD_WIDTH = 320;
    const FIELD_HEIGHT = 160;

    let left_alliance = $derived(swap ? Alliance.RED : Alliance.BLUE);
    let right_alliance = $derived(swap ? Alliance.BLUE : Alliance.RED);

    let svg: SVGSVGElement | undefined = $state();

    function clamp(value: number): number {
        return Math.min(Math.max(value, 0), 1);
    }

    function handleClick(event: MouseEvent) {
        if (!editable || !svg) {
            return;
        }
        // Map through the SVG's own transform so the marker lands where the operator
        // tapped whatever letterboxing the current box size produces.
        const ctm = svg.getScreenCTM();
        if (!ctm) {
            return;
        }
        const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(
            ctm.inverse(),
        );
        onSetCoordinates?.({
            x: clamp(point.x / FIELD_WIDTH),
            y: clamp(point.y / FIELD_HEIGHT),
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
    <svg bind:this={svg} viewBox="0 0 {FIELD_WIDTH} {FIELD_HEIGHT}">
        <rect x="0" y="0" width="320" height="160" class="carpet" />
        <rect x="0" y="0" width="70" height="160" class="zone {left_alliance}" />
        <rect x="250" y="0" width="70" height="160" class="zone {right_alliance}" />
        <line x1="160" y1="0" x2="160" y2="160" class="centerline" />
        <circle cx="160" cy="80" r="26" class="hub" />
        {#if coordinates}
            <circle
                cx={coordinates.x * FIELD_WIDTH}
                cy={coordinates.y * FIELD_HEIGHT}
                r="7"
                class="marker"
            />
        {/if}
    </svg>
</button>

<style>
    /* The SVG letterboxes inside whatever box it is given, so the schematic keeps its
       proportions at any card size and the marker stays where it was placed */
    .field-map {
        display: block;
        padding: 0;
        position: relative;
        width: 100%;
        height: 100%;
        max-width: 420px;
        background: none;
    }

    .field-map.editable {
        cursor: crosshair;
    }

    svg {
        width: 100%;
        height: 100%;
        display: block;
        border-radius: 8px;
    }

    .editable svg {
        outline: 2px solid var(--green-action);
        outline-offset: -2px;
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
        fill: var(--auto-action);
        stroke: black;
        stroke-width: 2;
    }
</style>
