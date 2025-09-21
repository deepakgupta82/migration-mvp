/**
 * Tests for message validation and normalization utilities
 */

import {
  validateProjectId,
  normalizeProjectId,
  validateMessage,
  parseAndValidateMessage,
  messageMatchesCriteria
} from './messageValidation';
import {
  MessageType,
  StandardizedAssessmentMessage,
  StandardizedProcessingMessage,
  StandardizedLogMessage
} from '../types/messages';
