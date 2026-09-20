/* Progressive enhancement for the board — plan 001 §7.
 *
 * The one hand-written script in the project. No build step: this is the file
 * the browser runs. Everything it does is an enhancement, so a browser that
 * never runs it is left with a board that works — every summary open, the
 * steps scrollable.
 *
 * On a phone it does two things: collapses each summary to its title and
 * company until it is tapped, and turns the steps into one card at a time with
 * an arrow either side, so nothing has to be swiped sideways. On a laptop it
 * drives the same arrows a card at a time, standing in for the scrollbar the
 * stylesheet hides.
 *
 * At both widths it clamps a summary's notes to the first two, or four lines,
 * whichever comes first, and offers a toggle for the rest — but only when the
 * clamp is actually hiding something.
 *
 * It also moves the job description's control. Without it the block carries its
 * own bar; with it, a laptop hides bar and closed block alike and the summary
 * card's button opens it instead. The two controls drive the same `<details>`,
 * so `aria-expanded` follows the element rather than a count of clicks.
 */
(() => {
  "use strict";

  // Matches the breakpoint in assets/board.css. The stylesheet decides what the
  // phone looks like; this only decides when the behaviour changes with it.
  const PHONE = window.matchMedia("(max-width: 30rem)");
  const STILL = window.matchMedia("(prefers-reduced-motion: reduce)");

  // Matches `.notes__item:nth-child(n + 3)` in assets/board.css. The stylesheet
  // decides how much of the list shows; this only decides whether there is
  // anything left over to offer.
  const NOTES_SHOWN = 2;

  const root = document.documentElement;

  function setExpanded(card, expanded) {
    card.toggleAttribute("data-collapsed", !expanded);
    card
      .querySelector("[data-summary-toggle]")
      .setAttribute("aria-expanded", String(expanded));

    // A collapsed card has no height to measure, so the notes inside it can
    // only be sized once it is open.
    const block = expanded ? card.querySelector("[data-notes]") : null;
    if (block) {
      syncNotes(block);
    }
  }

  function setNotes(block, expanded) {
    block.toggleAttribute("data-notes-collapsed", !expanded);
    const toggle = block.querySelector("[data-notes-toggle]");
    toggle.setAttribute("aria-expanded", String(expanded));
    toggle.textContent = expanded ? "Fewer notes" : "All notes";
  }

  /* Whether the clamp is holding anything back, asked while it is on.
   *
   * Two limits, and only one of them can be counted: a third note is arithmetic,
   * but four lines is a height the browser works out, and one long note reaches
   * it before a third note does. */
  function spareNotes(block) {
    const list = block.querySelector("[data-notes-list]");
    return list.children.length > NOTES_SHOWN || list.scrollHeight > list.clientHeight + 1;
  }

  function syncNotes(block) {
    setNotes(block, false);
    const spare = spareNotes(block);

    block.querySelector("[data-notes-toggle]").hidden = !spare;
    if (!spare) {
      setNotes(block, true);
    }
  }

  function describes(button) {
    return document.getElementById(button.getAttribute("aria-controls"));
  }

  function describedBy(block) {
    return document.querySelector(`[aria-controls="${block.id}"]`);
  }

  function cards(steps) {
    return Array.from(steps.querySelector("[data-steps-track]").children);
  }

  function track(steps) {
    return steps.querySelector("[data-steps-track]");
  }

  function offsets(steps) {
    const all = cards(steps);
    return all.map((card) => card.offsetLeft - all[0].offsetLeft);
  }

  function scrollTrack(steps, left) {
    track(steps).scrollTo({ left, behavior: STILL.matches ? "auto" : "smooth" });
  }

  /* Where the track stands, and whether an arrow could move it.
   *
   * A phone keeps an index, because the card is the track and the reader taps
   * through a known list. A laptop reads the scroll position instead, because
   * the wheel and the trackpad still move the track and an index would go
   * stale the moment they did. */
  function position(steps) {
    const all = cards(steps);
    const element = track(steps);

    if (PHONE.matches) {
      const at = Number(element.dataset.stepsIndex || 0);
      return { start: at <= 0, end: at >= all.length - 1, movable: all.length > 1 };
    }

    const furthest = element.scrollWidth - element.clientWidth;
    return {
      start: element.scrollLeft <= 1,
      end: element.scrollLeft >= furthest - 1,
      movable: furthest > 1,
    };
  }

  function syncArrows(steps) {
    const { start, end, movable } = position(steps);
    const prev = steps.querySelector("[data-steps-prev]");
    const next = steps.querySelector("[data-steps-next]");

    if (PHONE.matches) {
      // A phone card is the width of the track, so hiding an arrow would
      // resize the card under the reader's thumb. The ends grey out instead.
      prev.hidden = next.hidden = !movable;
      prev.disabled = start;
      next.disabled = end;
      return;
    }

    // A laptop card is a fixed width, so an arrow can leave without moving
    // anything: it shows only while it has somewhere to go.
    prev.hidden = !movable || start;
    next.hidden = !movable || end;
    prev.disabled = next.disabled = false;
  }

  function showStep(steps, index) {
    const all = cards(steps);
    const wanted = Math.max(0, Math.min(all.length - 1, index));

    if (all.length > 0) {
      scrollTrack(steps, offsets(steps)[wanted]);
    }
    track(steps).dataset.stepsIndex = String(wanted);
    syncArrows(steps);
  }

  function move(steps, direction) {
    if (PHONE.matches) {
      showStep(steps, Number(track(steps).dataset.stepsIndex || 0) + direction);
      return;
    }

    // The next card edge past where the track stands, in the direction asked
    // for — so a click lands on a boundary however the track got here.
    const at = track(steps).scrollLeft;
    const edges = offsets(steps);
    const target =
      direction > 0
        ? edges.find((edge) => edge > at + 1)
        : edges.filter((edge) => edge < at - 1).pop();

    scrollTrack(steps, target === undefined ? at : target);
  }

  /* `toggle` fires whichever control opened the block, including the bar the
   * phone keeps, so the button is written from the element every time. */
  function onDetails(event) {
    const block = event.target;
    if (!(block instanceof Element) || !block.matches("[data-description]")) {
      return;
    }

    const button = describedBy(block);
    if (button) {
      button.setAttribute("aria-expanded", String(block.open));
    }
  }

  function apply() {
    document
      .querySelectorAll("[data-summary]")
      .forEach((card) => setExpanded(card, !PHONE.matches));
    document.querySelectorAll("[data-steps]").forEach((steps) => showStep(steps, 0));
    document.querySelectorAll("[data-description-toggle]").forEach((button) => {
      button.hidden = false;
      button.setAttribute("aria-expanded", String(describes(button).open));
    });
  }

  function onScroll(event) {
    const element = event.target;
    if (element instanceof Element && element.matches("[data-steps-track]")) {
      syncArrows(element.closest("[data-steps]"));
    }
  }

  function onClick(event) {
    const toggle = event.target.closest("[data-summary-toggle]");
    if (toggle) {
      const card = toggle.closest("[data-summary]");
      setExpanded(card, card.hasAttribute("data-collapsed"));
      return;
    }

    const notes = event.target.closest("[data-notes-toggle]");
    if (notes) {
      const block = notes.closest("[data-notes]");
      setNotes(block, block.hasAttribute("data-notes-collapsed"));
      return;
    }

    const description = event.target.closest("[data-description-toggle]");
    if (description) {
      const block = describes(description);
      // Only the element is set here; `onDetails` is what writes the button
      // back, so the phone's own bar and this one leave the same state behind.
      block.open = !block.open;
      return;
    }

    const arrow = event.target.closest("[data-steps-prev], [data-steps-next]");
    if (arrow) {
      move(arrow.closest("[data-steps]"), arrow.hasAttribute("data-steps-prev") ? -1 : 1);
    }
  }

  root.classList.add("has-js");
  // Delegated, so rows swapped in later are wired without re-running any of this.
  document.addEventListener("click", onClick);
  // Neither `scroll` nor `toggle` bubbles, so these listen on the way down.
  document.addEventListener("scroll", onScroll, true);
  document.addEventListener("toggle", onDetails, true);
  PHONE.addEventListener("change", apply);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply);
  } else {
    apply();
  }
})();
