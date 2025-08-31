import React, { useEffect, useRef, useState } from 'react';
import { Box, ScrollArea, Text, Loader } from '@mantine/core';
import { TerminalEntry } from './types';
import { formatTimestamp } from './utils';
import classes from './TerminalOutput.module.css';

interface TerminalOutputProps {
  entries: TerminalEntry[];
  containerRef: React.RefObject<HTMLDivElement>;
  onScroll: () => void;
  autoScrollEnabled: boolean;
  isUserScrolling: boolean;
}

const TerminalOutput: React.FC<TerminalOutputProps> = ({
  entries,
  containerRef,
  onScroll,
  autoScrollEnabled,
  isUserScrolling,
}) => {
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Handle scroll events
  useEffect(() => {
    const scrollElement = scrollAreaRef.current?.querySelector('[data-radix-scroll-area-viewport]');
    if (scrollElement) {
      scrollElement.addEventListener('scroll', onScroll);
      return () => scrollElement.removeEventListener('scroll', onScroll);
    }
  }, [onScroll]);

  // Auto-scroll to bottom when new entries arrive (if enabled and not user scrolling)
  useEffect(() => {
    if (autoScrollEnabled && !isUserScrolling && entries.length > 0) {
      const scrollElement = scrollAreaRef.current?.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollElement) {
        scrollElement.scrollTop = scrollElement.scrollHeight;
      }
    }
  }, [entries, autoScrollEnabled, isUserScrolling]);

  // Render individual terminal entry
  const renderEntry = (entry: TerminalEntry) => {
    return (
      <div key={entry.id} className={classes.entry}>
        {/* Timestamp */}
        <span className={classes.timestamp}>
          [{formatTimestamp(entry.timestamp)}]
        </span>

        {/* Icon */}
        {entry.icon && (
          <span className={classes.icon} style={{ color: entry.color }}>
            {entry.icon}
          </span>
        )}

        {/* Message content */}
        <div
          className={classes.message}
          style={{ color: entry.color }}
          dangerouslySetInnerHTML={{ __html: entry.formattedMessage }}
        />

        {/* Progress bar for progress entries */}
        {entry.type === 'progress' && entry.metadata?.progress_percentage !== undefined && (
          <div className={classes.progressContainer}>
            <div
              className={classes.progressBar}
              style={{
                width: `${Math.min(100, Math.max(0, entry.metadata.progress_percentage))}%`,
                backgroundColor: entry.color,
              }}
            />
            <span className={classes.progressText}>
              {entry.metadata.progress_percentage.toFixed(1)}%
            </span>
          </div>
        )}
      </div>
    );
  };

  return (
    <Box className={classes.output} ref={containerRef}>
      <ScrollArea
        h="100%"
        type="auto"
        ref={scrollAreaRef}
        className={classes.scrollArea}
      >
        <div className={classes.entriesContainer}>
          {entries.length === 0 ? (
            <div className={classes.emptyState}>
              <Text size="sm" c="dimmed" ta="center">
                No terminal entries yet. Waiting for CrewAI activity...
              </Text>
            </div>
          ) : (
            entries.map(renderEntry)
          )}

          {/* Loading indicator */}
          {isLoading && (
            <div className={classes.loading}>
              <Loader size="sm" />
              <Text size="xs" c="dimmed" ml="xs">
                Loading more entries...
              </Text>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Auto-scroll indicator */}
      {isUserScrolling && autoScrollEnabled && (
        <div className={classes.scrollIndicator}>
          <Text size="xs" c="dimmed">
            Scrolled up - auto-scroll paused
          </Text>
        </div>
      )}
    </Box>
  );
};

export default TerminalOutput;