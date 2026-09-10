/*
 * Minimal i.MX6UL pin-function and input-code definitions for huiyan-keys.
 *
 * The three mux tuples are copied verbatim from Embedfire's official
 * ebf-linux-dtoverlays include/imx6ul-pinfunc.h (commit cc6f87a, 2021-05-08).
 * Keeping this narrow header makes the standalone overlay reproducible
 * without copying an entire kernel header tree.
 */

#define MX6UL_PAD_UART3_TX_DATA__GPIO1_IO24 0x00a4 0x0330 0x0000 5 0
#define MX6UL_PAD_UART3_RX_DATA__GPIO1_IO25 0x00a8 0x0334 0x0000 5 0
#define MX6UL_PAD_UART3_CTS_B__GPIO1_IO26   0x00ac 0x0338 0x0000 5 0

/* GPIO_ACTIVE_LOW from dt-bindings/gpio/gpio.h. */
#define GPIO_ACTIVE_LOW 1

/* KEY_PROG1/2/3 from Linux input-event-codes.h: 148, 149 and 202. */
#define KEY_PROG1 148
#define KEY_PROG2 149
#define KEY_PROG3 202

/*
 * i.MX6UL input pad control: HYS | PUS_100K_UP | PUE | PKE |
 * SPEED_MED | DSE_40ohm | SRE_FAST = 0x0001b0b1.
 * PUE includes PKE on i.MX6UL, so this enables an internal 100K pull-up.
 */
#define HUIYAN_PAD_CTL_INPUT_PULL_UP 0x0001b0b1
