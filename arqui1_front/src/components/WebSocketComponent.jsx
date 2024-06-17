import React, { useEffect, useState, useRef } from 'react';
import styled, { createGlobalStyle, keyframes } from 'styled-components';
import { FaLightbulb, FaDoorClosed, FaDoorOpen, FaExclamationTriangle, FaUsers, FaMotorcycle, FaSun, FaMoon } from 'react-icons/fa';

// Global Styles
const GlobalStyle = createGlobalStyle`
  body {
    transition: background-color 0.5s, color 0.5s;
  }

  body.night-mode {
    background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
    color: #e5e5e5;
  }

  body.day-mode {
    background: linear-gradient(135deg, #FFDEE9, #B5FFFC);
    color: #333;
  }
`;

const Container = styled.div`
  text-align: center;
  padding: 2em;
  transition: background-color 0.3s, color 0.3s;
`;

const Title = styled.h2`
  margin-bottom: 1em;
  font-size: 2.5em;
  color: #333;
`;

const Button = styled.button`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 1em;
  padding: 0.5em 1.5em;
  margin: 0.5em;
  border: none;
  border-radius: 25px;
  background-color: #61dafb;
  color: white;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  transition: background-color 0.3s, transform 0.3s, box-shadow 0.3s;

  &:hover {
    background-color: #21a1f1;
    transform: scale(1.05);
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
  }

  &:active {
    transform: scale(0.95);
  }

  &.active {
    background-color: #21a1f1;
  }
`;

const StatusContainer = styled.div`
  margin: 2em 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1em;
`;

const StatusItem = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1em;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  transition: background-color 0.3s, box-shadow 0.3s;

  &:hover {
    background: rgba(255, 255, 255, 0.2);
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
  }

  svg {
    margin-right: 0.5em;
  }
`;

const Room = styled.div`
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
`;

const RoomButton = styled(Button)`
  width: 150px;
  height: 150px;
  flex-direction: column;
  margin: 10px;
`;

const pulse = keyframes`
  0% {
    box-shadow: 0 0 0 0 rgba(33, 161, 241, 0.7);
  }
  70% {
    box-shadow: 0 0 10px 20px rgba(33, 161, 241, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(33, 161, 241, 0);
  }
`;

const AnimatedBackground = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: -1;
  pointer-events: none;
  animation: ${pulse} 2s infinite;
`;

const WebSocketComponent = () => {
  const [ledStates, setLedStates] = useState(Array(8).fill(false));
  const [lightStatus, setLightStatus] = useState(0);
  const [servoState, setServoState] = useState(false);
  const [peopleCount, setPeopleCount] = useState(0);
  const [alarmActive, setAlarmActive] = useState(false);
  const [outsideLedAuto, setOutsideLedAuto] = useState(false);
  const [rcMotorState, setRcMotorState] = useState(false);
  const socketRef = useRef(null);

  useEffect(() => {
    socketRef.current = new WebSocket('ws://192.168.50.187:8000/ws');

    socketRef.current.onopen = () => {
      console.log('WebSocket connection established');
    };

    socketRef.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.initial_states) {
        setLedStates(message.initial_states);
        setServoState(message.servo_state);
        setPeopleCount(message.people_count);
        setRcMotorState(message.rc_motor_state);
      } else if (message.led_index !== undefined) {
        setLedStates((prevStates) => {
          const newStates = [...prevStates];
          newStates[message.led_index] = message.state;
          return newStates;
        });
      } else if (message.light_status !== undefined) {
        setLightStatus(!message.light_status);
        document.body.classList.toggle('night-mode', message.light_status === 1);
        document.body.classList.toggle('day-mode', message.light_status !== 1);
      } else if (message.servo_state !== undefined) {
        setServoState(message.servo_state);
      } else if (message.people_count !== undefined) {
        setPeopleCount(message.people_count);
      } else if (message.alarm !== undefined) {
        setAlarmActive(message.alarm);
      } else if (message.outside_led_auto !== undefined) {
        setOutsideLedAuto(message.outside_led_auto);
      } else if (message.rc_motor_state !== undefined) {
        setRcMotorState(message.rc_motor_state);
      }
    };

    socketRef.current.onclose = () => {
      console.log('WebSocket connection closed');
    };

    return () => {
      socketRef.current.close();
    };
  }, []);

  const toggleLed = (ledIndex) => {
    if (socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ led_index: ledIndex }));
    }
  };

  const toggleServo = () => {
    if (socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ servo: true }));
    }
  };

  const toggleRcMotor = () => {
    if (socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ rc_motor: true }));
    }
  };
  const cuartos = ["BAÑO", "CARGA-DESCARGA", "COMEDOR", "AREA-TRABAJO", "CONFERENCIA", "ADMINISTRACION", "RECEPCION", "EXTERIOR"]

  return (
    <Container>
      <GlobalStyle />
      <AnimatedBackground />
      <Title>Smart Home Control Panel</Title>
      <Room>
        {ledStates.map((state, index) => (
          <RoomButton key={index} onClick={() => toggleLed(index)} className={state ? 'active' : ''}>
            <FaLightbulb size={40} />
            <span>{`${cuartos[index]}`}</span>
            <span>{state ? 'On' : 'Off'}</span>
          </RoomButton>
        ))}
      </Room>
      <Button onClick={toggleServo}>
        {servoState ? <FaDoorClosed /> : <FaDoorOpen />} {servoState ? 'Close Door' : 'Open Door'}
      </Button>
      <Button onClick={toggleRcMotor}>
        <FaMotorcycle /> {rcMotorState ? 'Turn RC Motor Off' : 'Turn RC Motor On'}
      </Button>
      <StatusContainer>
        <StatusItem>
          {lightStatus ? <FaSun /> : <FaMoon />} Light Sensor Status: {lightStatus ? 'Light Detected' : 'No Light'}
        </StatusItem>
        <StatusItem>
          <FaUsers /> People Count: {peopleCount}
        </StatusItem>
        <StatusItem>
          <FaExclamationTriangle /> Alarm Status: {alarmActive ? 'Alarm Active' : 'Alarm Inactive'}
        </StatusItem>
        <StatusItem>
          <FaLightbulb /> Outside LED Status: {outsideLedAuto ? 'Automatic Control (Night)' : 'Manual Control (Day)'}
        </StatusItem>
      </StatusContainer>
    </Container>
  );
};

export default WebSocketComponent;
