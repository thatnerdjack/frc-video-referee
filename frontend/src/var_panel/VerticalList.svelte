<script lang="ts" generics="T">
    import type { Snippet } from "svelte";

    interface Props {
        item: Snippet<[T]>;
        key_func: (item: T) => any;
        data: T[];
        /** Shown in place of the list when there is nothing to display */
        empty_message?: string;
    }

    let { item, key_func, data, empty_message }: Props = $props();
</script>

<div class="scroll-container">
    {#if data.length === 0 && empty_message}
        <div class="empty">{empty_message}</div>
    {:else}
        <div class="list">
            {#each data as value (key_func(value))}
                {@render item(value)}
            {/each}
        </div>
    {/if}
</div>

<style>
    .scroll-container {
        height: 100%;
        min-height: 0;
        /* The parent switches the list between a column and a row on narrow screens */
        overflow-y: var(--list-overflow-y, auto);
        overflow-x: var(--list-overflow-x, hidden);
        padding: 10px 0;
        -webkit-overflow-scrolling: touch;
    }

    .list {
        display: flex;
        flex-direction: var(--list-direction, column);
        gap: 10px;
        min-height: 0;
    }

    .empty {
        color: var(--text-inactive-dark);
        font-size: 0.9em;
        padding: 1em 0.5em;
    }
</style>
