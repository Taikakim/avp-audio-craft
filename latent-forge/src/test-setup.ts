// Registers @testing-library/jest-dom's matchers (toHaveValue, toHaveClass, toHaveAttribute, ...)
// on vitest's expect, for every test file. Importing it in a node-environment test is harmless.
import "@testing-library/jest-dom/vitest";
